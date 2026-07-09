"""HYDRA-PRIME master fusion engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .math_utils import clamp, mean, sign
from .models import (
    CotSnapshot,
    DarkPoolSnapshot,
    Decision,
    OHLCVBar,
    OptionSnapshot,
    PhysicalSnapshot,
    PositionPlan,
    PriceTick,
    SignalResult,
    TradeTick,
)
from .risk import RiskLimits, RiskManager
from .signals import (
    CrossAssetLeadDetector,
    DarkPoolBlockTradeDetector,
    InstitutionalFootprintTracker,
    OptionsFlowAnomalyDetector,
    PhysicalWorldSensor,
    VPINCalculator,
    VolatilitySqueezeDetector,
    CorrelationDivergenceDetector,
)


DEFAULT_WEIGHTS: Dict[str, float] = {
    "VPIN_TOXICITY": 0.25,
    "CROSS_ASSET_LEAD": 0.22,
    "CORRELATION_DIVERGENCE": 0.16,
    "DARK_POOL_BLOCK": 0.12,
    "OPTIONS_FLOW": 0.10,
    "COT_VELOCITY": 0.08,
    "PHYSICAL_WORLD": 0.07,
    # Squeeze is an amplifier, not a directional vote.
    "VOLATILITY_SQUEEZE": 0.00,
}


@dataclass(frozen=True)
class FusionConfig:
    """Configuration for the AND-gated pre-movement fusion logic."""

    score_threshold: float = 70.0
    min_independent_signals: int = 3
    min_confidence_per_signal: float = 0.20
    squeeze_max_boost: float = 0.18
    execution_enabled: bool = False
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))


class PreMovementFusionEngine:
    """Convert independent signal results into one decision per instrument.

    The scoring model deliberately rewards *agreement* more than raw count. A
    signal does not fire because one detector is loud; it fires when multiple
    independent causes point in the same direction. Execution is disabled by
    default: this engine emits opportunity alerts only.
    """

    def __init__(self, risk_manager: RiskManager, config: Optional[FusionConfig] = None) -> None:
        self.risk_manager = risk_manager
        self.config = config or FusionConfig()

    def _weight(self, signal_type: str) -> float:
        return float(self.config.weights.get(signal_type, 0.05))

    @staticmethod
    def _lead_time_label(votes: Sequence[SignalResult]) -> str:
        mins = [v.lead_time_minutes for v in votes if v.lead_time_minutes is not None and v.direction != 0]
        if not mins:
            labels = [v.lead_time for v in votes if v.direction != 0 and v.lead_time]
            return ", ".join(sorted(set(labels))) if labels else "Unknown"
        fastest = min(mins)
        slowest = max(mins)
        if fastest < 60 and slowest < 60:
            return f"{fastest:.0f}-{slowest:.0f} minutes"
        if fastest < 60:
            return f"{fastest:.0f} minutes to {slowest/60:.1f} hours"
        if slowest < 24 * 60:
            return f"{fastest/60:.1f}-{slowest/60:.1f} hours"
        return f"{fastest/1440:.1f}-{slowest/1440:.1f} days"

    def fuse(
        self,
        instrument: str,
        signals: Sequence[SignalResult],
        reference_price: Optional[float] = None,
    ) -> Decision:
        active = [
            s
            for s in signals
            if s.instrument == instrument
            and s.active
            and s.confidence >= self.config.min_confidence_per_signal
        ]
        directional = [s for s in active if s.direction != 0]
        squeezes = [s for s in active if s.signal_type == "VOLATILITY_SQUEEZE"]

        if not directional:
            disabled_plan = PositionPlan(
                instrument=instrument,
                direction=0,
                leverage=0.0,
                risk_pct=0.0,
                stop_loss_pct=0.0,
                take_profit_pct=0.0,
                max_loss_dollars=0.0,
                notional_size=0.0,
                blocked=True,
                reason="Execution disabled: opportunity alerts only",
            )
            return Decision(
                instrument=instrument,
                direction=0,
                pre_move_score=0.0,
                fire=False,
                n_signals=0,
                n_independent=0,
                n_agreeing=0,
                bull_score=0.0,
                bear_score=0.0,
                lead_time_estimate="Unknown",
                position=disabled_plan,
                votes=[],
                squeeze_active=bool(squeezes),
                details={"reason": "No active directional pre-movement opportunity signals"},
            )

        weighted_votes: List[Tuple[SignalResult, float]] = []
        for s in directional:
            weight = self._weight(s.signal_type)
            # Strength is allowed to boost or damp confidence, but the signal's
            # own confidence remains the primary normalised reliability measure.
            weighted_value = weight * s.confidence * (0.65 + 0.35 * clamp(s.strength, 0.0, 1.0))
            weighted_votes.append((s, weighted_value))

        bull_score = sum(w for s, w in weighted_votes if s.direction > 0)
        bear_score = sum(w for s, w in weighted_votes if s.direction < 0)
        total_abs = bull_score + bear_score
        net = bull_score - bear_score
        direction = sign(net, deadband=1e-12)
        if total_abs <= 0 or direction == 0:
            score = 0.0
            n_agreeing = 0
            winning_votes: List[SignalResult] = []
        else:
            winning_votes = [s for s, _ in weighted_votes if sign(s.direction) == direction]
            losing_votes = [s for s, _ in weighted_votes if sign(s.direction) == -direction]
            n_agreeing = len(set(s.signal_type for s in winning_votes))
            n_independent_total = len(set(s.signal_type for s in directional))
            alignment = abs(net) / total_abs
            mean_winning_conf = mean([s.confidence for s in winning_votes], 0.0)
            # Penalise if the required AND-gate has not been met. Once 3 signals
            # agree, additional independent confirmations give a controlled boost.
            convergence_gate = min(1.0, n_agreeing / max(1, self.config.min_independent_signals))
            extra_confirmation = 1.0 + 0.06 * max(0, n_agreeing - self.config.min_independent_signals)
            conflict_penalty = 1.0 - min(0.35, 0.10 * len(losing_votes))
            squeeze_strength = max([s.confidence for s in squeezes], default=0.0)
            squeeze_boost = 1.0 + self.config.squeeze_max_boost * squeeze_strength
            # This produces high scores only when signals are directional,
            # confident, aligned and numerous enough to pass the AND gate.
            score = 100.0 * alignment * (0.50 + 0.50 * mean_winning_conf) * convergence_gate
            score *= extra_confirmation * conflict_penalty * squeeze_boost
            score = clamp(score, 0.0, 100.0)

        n_independent = len(set(s.signal_type for s in directional))
        n_agreeing_independent = len(set(s.signal_type for s in directional if sign(s.direction) == direction)) if direction else 0
        fire_without_risk = (
            score >= self.config.score_threshold
            and n_agreeing_independent >= self.config.min_independent_signals
            and direction != 0
        )
        if self.config.execution_enabled:
            plan = self.risk_manager.position_plan(instrument, direction if fire_without_risk else 0, score, reference_price)
            fire = fire_without_risk and not plan.blocked
        else:
            # Execution remains disabled, but the alert still includes advisory
            # execution parameters so the user knows the suggested leverage,
            # notional, risk, stop, target, and max loss if they choose to act
            # outside HYDRA-PRIME.
            plan = self.risk_manager.advisory_position_plan(
                instrument,
                direction if fire_without_risk else 0,
                score,
                reference_price,
            )
            fire = fire_without_risk

        warnings: List[str] = []
        if self.config.execution_enabled and fire_without_risk and plan.blocked:
            warnings.append(plan.reason)
        if n_agreeing_independent < self.config.min_independent_signals:
            warnings.append(
                f"AND gate not met: {n_agreeing_independent}/{self.config.min_independent_signals} agreeing independent signals"
            )
        if score < self.config.score_threshold:
            warnings.append(f"Score below threshold: {score:.1f} < {self.config.score_threshold:.1f}")

        return Decision(
            instrument=instrument,
            direction=direction if fire_without_risk else (direction if score > 0 else 0),
            pre_move_score=round(score, 1),
            fire=fire,
            n_signals=len(directional),
            n_independent=n_independent,
            n_agreeing=n_agreeing_independent,
            bull_score=round(bull_score, 5),
            bear_score=round(bear_score, 5),
            lead_time_estimate=self._lead_time_label(winning_votes if direction else directional),
            position=plan,
            votes=list(directional),
            squeeze_active=bool(squeezes),
            warnings=warnings,
            details={
                "active_signal_count": len(active),
                "directional_signal_count": len(directional),
                "squeeze_count": len(squeezes),
            },
        )


class HydraPrimeEngine:
    """Complete HYDRA-PRIME opportunity-alert system: ingestion, detectors and fusion.

    Broker execution is intentionally absent. The engine reports that an
    opportunity has been detected; it does not place, route, or simulate trades.
    """

    def __init__(
        self,
        instruments: Optional[Iterable[str]] = None,
        capital: float = 10_000.0,
        fusion_config: Optional[FusionConfig] = None,
        risk_limits: Optional[RiskLimits] = None,
    ) -> None:
        self.instruments = list(
            instruments
            or ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "HG"]
        )
        self.cross_asset = CrossAssetLeadDetector()
        self.options_flow = OptionsFlowAnomalyDetector()
        self.dark_pool = DarkPoolBlockTradeDetector()
        self.vpin = VPINCalculator()
        self.squeeze = VolatilitySqueezeDetector()
        self.correlation = CorrelationDivergenceDetector()
        self.cot = InstitutionalFootprintTracker()
        self.physical = PhysicalWorldSensor()
        self.risk_manager = RiskManager(capital=capital, limits=risk_limits or RiskLimits())
        self.fusion = PreMovementFusionEngine(self.risk_manager, fusion_config)
        self.latest_prices: Dict[str, float] = {}

    # ----------------------------- ingestion -----------------------------

    def ingest_price(self, tick: PriceTick) -> None:
        self.latest_prices[tick.symbol] = tick.price
        self.cross_asset.update_tick(tick)

    def ingest_trade(self, trade: TradeTick) -> None:
        self.latest_prices[trade.symbol] = trade.price
        self.vpin.update_trade(trade)

    def ingest_bar(self, bar: OHLCVBar) -> None:
        self.latest_prices[bar.symbol] = bar.close
        self.squeeze.update_bar(bar)
        self.correlation.update_bar(bar)
        # Cross-asset lead also benefits from bar closes for slower feeds.
        self.cross_asset.update_price(bar.symbol, bar.close, bar.timestamp)

    def ingest_options(self, snapshot: OptionSnapshot) -> None:
        self.options_flow.update_snapshot(snapshot)
        if snapshot.underlying_price:
            self.latest_prices[snapshot.instrument] = snapshot.underlying_price

    def ingest_dark_pool(self, snapshot: DarkPoolSnapshot) -> None:
        self.dark_pool.update_snapshot(snapshot)
        if snapshot.close:
            self.latest_prices[snapshot.instrument] = snapshot.close

    def ingest_cot(self, snapshot: CotSnapshot) -> None:
        self.cot.update_snapshot(snapshot)

    def ingest_physical(self, snapshot: PhysicalSnapshot) -> None:
        self.physical.update_snapshot(snapshot)

    # ----------------------------- evaluation -----------------------------

    def collect_signals(self) -> List[SignalResult]:
        signals: List[SignalResult] = []
        for detector in (
            self.cross_asset,
            self.options_flow,
            self.dark_pool,
            self.vpin,
            self.squeeze,
            self.correlation,
            self.cot,
            self.physical,
        ):
            signals.extend(detector.evaluate(self.instruments))
        return signals

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[Decision]:
        target = list(instruments or self.instruments)
        signals = self.collect_signals()
        decisions = []
        for instrument in target:
            decisions.append(
                self.fusion.fuse(
                    instrument,
                    signals,
                    reference_price=self.latest_prices.get(instrument),
                )
            )
        return decisions

    def alerts(self, instruments: Optional[Iterable[str]] = None) -> List[Decision]:
        return [d for d in self.evaluate(instruments) if d.fire]

    def diagnostics(self) -> Dict[str, object]:
        signals = self.collect_signals()
        by_type: Dict[str, int] = defaultdict(int)
        active_by_type: Dict[str, int] = defaultdict(int)
        for s in signals:
            by_type[s.signal_type] += 1
            if s.active:
                active_by_type[s.signal_type] += 1
        return {
            "instruments": list(self.instruments),
            "latest_prices": dict(self.latest_prices),
            "signals_total": len(signals),
            "signals_by_type": dict(by_type),
            "active_signals_by_type": dict(active_by_type),
            "output_mode": {
                "opportunity_alerts_only": True,
                "advisory_trade_parameters_included": True,
                "broker_execution": False,
                "order_routing": False,
                "simulated_fills": False,
            },
        }
