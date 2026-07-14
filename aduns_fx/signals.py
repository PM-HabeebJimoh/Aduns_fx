"""The eight HYDRA-PRIME pre-movement signal detectors.

The detectors do not place trades. They convert observable leading evidence
into normalised `SignalResult` objects which are fused by the engine.

Implemented signals:
1. Cross-asset temporal lead detection
2. Options-flow anomaly detection
3. Dark-pool / block-trade footprint detection
4. VPIN order-flow toxicity / informed trading detection
5. Entropy collapse + volatility squeeze detection
6. Cross-market correlation divergence detection
7. Institutional footprint / COT velocity tracking
8. Physical-world supply-demand sensor fusion
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Tuple

from .math_utils import (
    atr,
    bollinger_widths,
    clamp,
    correlation,
    linear_slope,
    log_returns,
    mean,
    normalised_sign_entropy,
    pct_change,
    percentile_rank,
    rolling_correlations,
    safe_div,
    sign,
    simple_returns,
    std,
    z_score,
)
from .models import (
    CotSnapshot,
    DarkPoolSnapshot,
    Direction,
    OHLCVBar,
    OptionSnapshot,
    PhysicalSnapshot,
    PriceTick,
    SignalResult,
    TradeTick,
    utcnow,
)


# ---------------------------------------------------------------------------
# SIGNAL 1: Cross-asset temporal lead detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeadPair:
    leader: str
    follower: str
    relationship: int
    lag_minutes: float
    description: str = ""


DEFAULT_LEAD_PAIRS: Tuple[LeadPair, ...] = (
    LeadPair("BTC", "XAUUSD", +1, 480, "Weekend/liquidity risk proxy leads gold"),
    LeadPair("PAXG", "XAUUSD", +1, 60, "Tokenised gold leads spot gold"),
    LeadPair("XAUUSD", "XAGUSD", +1, 20, "Gold leads silver"),
    LeadPair("TNX", "USDJPY", +1, 45, "10Y yield leads USDJPY"),
    LeadPair("TNX", "XAUUSD", -1, 60, "10Y yield inverse gold"),
    LeadPair("DXY", "EURUSD", -1, 5, "DXY inverse EURUSD"),
    LeadPair("DXY", "XAUUSD", -1, 10, "DXY inverse gold"),
    LeadPair("HG", "AUDUSD", +1, 30, "Copper leads AUD"),
    LeadPair("SPX", "AUDUSD", +1, 15, "Equity risk leads AUD"),
    LeadPair("SPX", "USDJPY", +1, 20, "Equity risk leads USDJPY"),
)


class CrossAssetLeadDetector:
    """Detect statistically significant moves in leaders before followers move."""

    signal_type = "CROSS_ASSET_LEAD"

    def __init__(
        self,
        lead_pairs: Sequence[LeadPair] = DEFAULT_LEAD_PAIRS,
        maxlen: int = 500,
        z_threshold: float = 2.0,
        recent_points: int = 5,
    ) -> None:
        self.lead_pairs = tuple(lead_pairs)
        self.maxlen = maxlen
        self.z_threshold = z_threshold
        self.recent_points = recent_points
        self.prices: Dict[str, Deque[PriceTick]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update_price(self, symbol: str, price: float, timestamp: Optional[datetime] = None) -> None:
        self.prices[symbol].append(PriceTick(symbol=symbol, price=float(price), timestamp=timestamp or utcnow()))

    def update_tick(self, tick: PriceTick) -> None:
        self.prices[tick.symbol].append(tick)

    def _leader_move(self, leader: str) -> Dict[str, float]:
        buf = list(self.prices.get(leader, ()))
        if len(buf) < max(12, self.recent_points + 5):
            return {"move": False, "z": 0.0, "direction": 0, "recent_return": 0.0}
        prices = [t.price for t in buf if t.price > 0]
        if len(prices) < max(12, self.recent_points + 5):
            return {"move": False, "z": 0.0, "direction": 0, "recent_return": 0.0}

        returns = log_returns(prices)
        if len(returns) < 10:
            return {"move": False, "z": 0.0, "direction": 0, "recent_return": 0.0}
        recent_return = prices[-1] / prices[-self.recent_points] - 1.0
        # Multi-tick move versus single-tick dispersion. This intentionally
        # fires only when a leader has moved enough to clear noise.
        z = recent_return / max(std(returns), 1e-12)
        direction = sign(z)
        return {
            "move": abs(z) >= self.z_threshold,
            "z": z,
            "direction": direction,
            "recent_return": recent_return,
        }

    def _follower_absorbed_move(self, follower: str, expected_direction: int) -> bool:
        """Return True when the follower already moved materially in expected direction.

        The detector is a *pre*-movement detector; if the follower already made a
        comparable move, the edge window is assumed to have decayed.
        """

        buf = list(self.prices.get(follower, ()))
        if len(buf) < self.recent_points + 5:
            return False
        prices = [t.price for t in buf if t.price > 0]
        if len(prices) < self.recent_points + 5:
            return False
        follower_ret = prices[-1] / prices[-self.recent_points] - 1.0
        return sign(follower_ret, deadband=0.0005) == expected_direction and abs(follower_ret) > 0.002

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        raw: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for pair in self.lead_pairs:
            if allowed is not None and pair.follower not in allowed:
                continue
            move = self._leader_move(pair.leader)
            if not move["move"]:
                continue
            expected_direction = int(move["direction"]) * int(pair.relationship)
            if expected_direction == 0:
                continue
            absorbed = self._follower_absorbed_move(pair.follower, expected_direction)
            confidence = clamp(abs(float(move["z"])) / 4.0, 0.05, 1.0)
            if absorbed:
                confidence *= 0.35
            raw[pair.follower].append(
                {
                    "leader": pair.leader,
                    "relationship": pair.relationship,
                    "expected_direction": expected_direction,
                    "confidence": confidence,
                    "lag_minutes": pair.lag_minutes,
                    "leader_z": move["z"],
                    "recent_return": move["recent_return"],
                    "absorbed": absorbed,
                    "description": pair.description,
                }
            )

        results: List[SignalResult] = []
        for follower, items in raw.items():
            bull = sum(float(i["confidence"]) for i in items if int(i["expected_direction"]) > 0)
            bear = sum(float(i["confidence"]) for i in items if int(i["expected_direction"]) < 0)
            total = bull + bear
            if total <= 0:
                continue
            direction_score = (bull - bear) / total
            direction = sign(direction_score, deadband=0.20)
            n_leaders = len(items)
            confidence = clamp(abs(direction_score) * mean([float(i["confidence"]) for i in items]), 0.0, 1.0)
            # A second confirming leader gives a true cascade boost.
            confidence = clamp(confidence * (1.0 + 0.15 * max(0, n_leaders - 1)), 0.0, 1.0)
            lead_min = min(float(i["lag_minutes"]) for i in items)
            lead_max = max(float(i["lag_minutes"]) for i in items)
            active = direction != 0 and confidence >= 0.25
            results.append(
                SignalResult(
                    signal_type=self.signal_type,
                    instrument=follower,
                    direction=direction,
                    confidence=confidence,
                    strength=clamp(total / max(1.0, n_leaders), 0.0, 1.0),
                    active=active,
                    lead_time=f"{lead_min:.0f}-{lead_max:.0f} minutes",
                    lead_time_minutes=lead_min,
                    source="lead_pair_cascade",
                    details={
                        "direction_score": direction_score,
                        "bull_confidence": bull,
                        "bear_confidence": bear,
                        "n_leading_signals": n_leaders,
                        "leaders": items,
                    },
                )
            )
        return results


# ---------------------------------------------------------------------------
# SIGNAL 2: Options-flow anomaly detector
# ---------------------------------------------------------------------------


class OptionsFlowAnomalyDetector:
    """Detect put/call, OTM-volume and skew anomalies before underlying moves."""

    signal_type = "OPTIONS_FLOW"

    def __init__(self, maxlen: int = 120) -> None:
        self.history: Dict[str, Deque[OptionSnapshot]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update_snapshot(self, snapshot: OptionSnapshot) -> None:
        self.history[snapshot.instrument].append(snapshot)

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        results: List[SignalResult] = []
        for instrument, hist_deque in self.history.items():
            if allowed is not None and instrument not in allowed:
                continue
            hist = list(hist_deque)
            if not hist:
                continue
            latest = hist[-1]
            components: List[Tuple[str, float, Dict[str, float]]] = []
            pcr = latest.put_call_ratio
            if pcr < 0.40:
                components.append(("extreme_call_demand", +0.85, {"put_call_ratio": pcr}))
            elif pcr > 2.00:
                components.append(("extreme_put_demand", -0.85, {"put_call_ratio": pcr}))
            elif pcr < 0.65:
                components.append(("call_demand", +0.35, {"put_call_ratio": pcr}))
            elif pcr > 1.50:
                components.append(("put_demand", -0.35, {"put_call_ratio": pcr}))

            if len(hist) >= 2:
                prev_pcr = hist[-2].put_call_ratio
                if prev_pcr not in (0.0, float("inf")):
                    change = pct_change(prev_pcr, pcr)
                    if abs(change) >= 0.50:
                        # PCR down = calls gaining share = bullish; PCR up = puts gaining share = bearish.
                        components.append(("pcr_regime_shift", -sign(change) * 0.45, {"pcr_change": change}))

            rr = latest.risk_reversal_25d
            if rr is not None:
                if rr >= 5.0:
                    components.append(("bullish_25d_risk_reversal", +0.75, {"risk_reversal": rr}))
                elif rr <= -5.0:
                    components.append(("bearish_25d_risk_reversal", -0.75, {"risk_reversal": rr}))

            otm_call_hist = [s.otm_call_volume for s in hist[:-1]]
            otm_put_hist = [s.otm_put_volume for s in hist[:-1]]
            call_z = z_score(latest.otm_call_volume, otm_call_hist) if len(otm_call_hist) >= 5 else 0.0
            put_z = z_score(latest.otm_put_volume, otm_put_hist) if len(otm_put_hist) >= 5 else 0.0
            if call_z >= 2.5 or (latest.otm_call_volume > 0 and latest.otm_call_volume >= 2.5 * max(latest.otm_put_volume, 1.0)):
                components.append(("otm_call_surge", +clamp(max(call_z, 2.5) / 4.0, 0.45, 1.0), {"otm_call_z": call_z}))
            if put_z >= 2.5 or (latest.otm_put_volume > 0 and latest.otm_put_volume >= 2.5 * max(latest.otm_call_volume, 1.0)):
                components.append(("otm_put_surge", -clamp(max(put_z, 2.5) / 4.0, 0.45, 1.0), {"otm_put_z": put_z}))

            signed = sum(c[1] for c in components)
            direction = sign(signed, deadband=0.15)
            confidence = clamp(abs(signed) / 2.2, 0.0, 1.0)
            active = direction != 0 and confidence >= 0.25
            if components or allowed is not None:
                results.append(
                    SignalResult(
                        signal_type=self.signal_type,
                        instrument=instrument,
                        direction=direction,
                        confidence=confidence,
                        strength=clamp(abs(signed), 0.0, 1.0),
                        active=active,
                        lead_time="4-72 hours",
                        lead_time_minutes=240,
                        source="options_snapshot",
                        details={
                            "put_call_ratio": pcr,
                            "call_put_ratio": latest.call_put_ratio,
                            "risk_reversal_25d": rr,
                            "otm_call_z": call_z,
                            "otm_put_z": put_z,
                            "components": components,
                        },
                    )
                )
        return results


# ---------------------------------------------------------------------------
# SIGNAL 3: Dark-pool / block-trade footprint detector
# ---------------------------------------------------------------------------


class DarkPoolBlockTradeDetector:
    """Detect off-exchange/block volume and short-squeeze footprints."""

    signal_type = "DARK_POOL_BLOCK"

    def __init__(self, maxlen: int = 120) -> None:
        self.history: Dict[str, Deque[DarkPoolSnapshot]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update_snapshot(self, snapshot: DarkPoolSnapshot) -> None:
        self.history[snapshot.instrument].append(snapshot)

    @staticmethod
    def _snapshot_direction(latest: DarkPoolSnapshot, hist: Sequence[DarkPoolSnapshot]) -> int:
        if latest.block_buy_ratio is not None:
            return sign(latest.block_buy_ratio - 0.50, deadband=0.05)
        closes = [s.close for s in hist if s.close is not None]
        if len(closes) >= 2:
            return sign(closes[-1] - closes[-2])
        return 0

    @staticmethod
    def _higher_lows(hist: Sequence[DarkPoolSnapshot], n: int = 3) -> bool:
        lows = [s.low for s in hist if s.low is not None]
        closes = [s.close for s in hist if s.close is not None]
        if len(lows) >= n:
            recent = lows[-n:]
            if all(recent[i] >= recent[i - 1] for i in range(1, len(recent))):
                return True
        if len(closes) >= n:
            return linear_slope(closes[-n:]) > 0
        return False

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        results: List[SignalResult] = []
        for instrument, hist_deque in self.history.items():
            if allowed is not None and instrument not in allowed:
                continue
            hist = list(hist_deque)
            if not hist:
                continue
            latest = hist[-1]
            components: List[Tuple[str, float, Dict[str, float]]] = []
            footprint_dir = self._snapshot_direction(latest, hist)

            ratios = [s.dark_pool_ratio for s in hist[:-1]]
            volume_hist = [s.dark_pool_volume for s in hist[:-1]]
            ratio = latest.dark_pool_ratio
            volume_z = z_score(latest.dark_pool_volume, volume_hist) if len(volume_hist) >= 5 else 0.0

            if ratio >= 0.60:
                components.append(("dark_pool_ratio_gt_60pct", (footprint_dir or 1) * 0.45, {"ratio": ratio}))
            elif ratio >= 0.50:
                components.append(("dark_pool_ratio_elevated", (footprint_dir or 1) * 0.25, {"ratio": ratio}))
            if volume_z >= 2.0:
                components.append(("dark_pool_volume_z", (footprint_dir or 1) * clamp(volume_z / 4.0, 0.35, 1.0), {"volume_z": volume_z}))

            short_ratio = latest.short_ratio
            if short_ratio >= 0.45 and self._higher_lows(hist):
                # High short volume unable to push price down = squeeze pressure.
                components.append(("short_squeeze_setup", +0.90, {"short_ratio": short_ratio}))
            elif short_ratio >= 0.60 and footprint_dir < 0:
                components.append(("aggressive_short_pressure", -0.45, {"short_ratio": short_ratio}))

            signed = sum(c[1] for c in components)
            direction = sign(signed, deadband=0.15)
            confidence = clamp(abs(signed) / 1.8, 0.0, 1.0)
            active = direction != 0 and confidence >= 0.25
            if components or allowed is not None:
                results.append(
                    SignalResult(
                        signal_type=self.signal_type,
                        instrument=instrument,
                        direction=direction,
                        confidence=confidence,
                        strength=clamp(abs(signed), 0.0, 1.0),
                        active=active,
                        lead_time="4-24 hours",
                        lead_time_minutes=240,
                        source="dark_pool_snapshot",
                        details={
                            "dark_pool_ratio": ratio,
                            "short_ratio": short_ratio,
                            "volume_z": volume_z,
                            "ratio_baseline": mean(ratios) if ratios else 0.0,
                            "footprint_direction": footprint_dir,
                            "components": components,
                        },
                    )
                )
        return results


# ---------------------------------------------------------------------------
# SIGNAL 4: VPIN / informed-trading detector
# ---------------------------------------------------------------------------


class VPINCalculator:
    """Volume-synchronised Probability of Informed Trading.

    This is an implementable approximation: trades are bucketed by equal volume
    over the current rolling trade window and the average buy/sell imbalance of
    recent buckets is converted into a toxicity signal.
    """

    signal_type = "VPIN_TOXICITY"

    def __init__(
        self,
        n_buckets: int = 50,
        max_trades: int = 10000,
        min_buckets: int = 10,
        toxic_threshold: float = 0.65,
        z_threshold: float = 1.5,
        vpin_window_trades: int = 400,
    ) -> None:
        self.n_buckets = n_buckets
        self.max_trades = max_trades
        self.min_buckets = min_buckets
        self.toxic_threshold = toxic_threshold
        self.z_threshold = z_threshold
        self.vpin_window_trades = vpin_window_trades
        self.trades: Dict[str, Deque[TradeTick]] = defaultdict(lambda: deque(maxlen=max_trades))
        self.vpin_history: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=300))

    def add_trade(
        self,
        symbol: str,
        price: float,
        volume: float,
        is_buy: Optional[bool] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[SignalResult]:
        trade = TradeTick(symbol=symbol, price=float(price), volume=float(volume), is_buy=is_buy, timestamp=timestamp or utcnow())
        return self.update_trade(trade)

    def update_trade(self, trade: TradeTick) -> Optional[SignalResult]:
        if trade.is_buy is None:
            prev = self.trades[trade.symbol][-1].price if self.trades[trade.symbol] else trade.price
            inferred = trade.price >= prev
            trade = TradeTick(trade.symbol, trade.price, trade.volume, inferred, trade.timestamp)
        self.trades[trade.symbol].append(trade)
        return self.evaluate_symbol(trade.symbol, append_history=True)

    def _volume_buckets(self, trades: Sequence[TradeTick]) -> List[Tuple[float, float]]:
        total_volume = sum(max(0.0, t.volume) for t in trades)
        if total_volume <= 0:
            return []
        bucket_size = total_volume / self.n_buckets
        if bucket_size <= 0:
            return []
        buckets: List[Tuple[float, float]] = []
        buy = 0.0
        sell = 0.0
        current = 0.0
        for t in trades:
            remaining = max(0.0, t.volume)
            while remaining > 1e-12:
                capacity = bucket_size - current
                take = min(remaining, capacity)
                if t.is_buy:
                    buy += take
                else:
                    sell += take
                current += take
                remaining -= take
                if current >= bucket_size - 1e-12:
                    buckets.append((buy, sell))
                    buy = sell = current = 0.0
        if current > bucket_size * 0.5:
            buckets.append((buy, sell))
        return buckets

    def evaluate_symbol(self, symbol: str, append_history: bool = False) -> Optional[SignalResult]:
        all_trades = list(self.trades.get(symbol, ()))
        if len(all_trades) < max(20, self.min_buckets):
            return None
        # VPIN is a *current toxicity* measure. Use a recent rolling trade
        # window for bucket construction while retaining a longer history for
        # baseline z-scores.
        trades = all_trades[-min(len(all_trades), self.vpin_window_trades) :]
        buckets = self._volume_buckets(trades)
        if len(buckets) < self.min_buckets:
            return None
        imbalances = [abs(b - s) / max(b + s, 1e-12) for b, s in buckets]
        recent_imbalances = imbalances[-self.n_buckets :]
        vpin = mean(recent_imbalances)
        hist = list(self.vpin_history[symbol])
        z = z_score(vpin, hist) if len(hist) >= 10 else 0.0
        if append_history:
            self.vpin_history[symbol].append(vpin)

        recent = trades[-min(200, len(trades)) :]
        buy_volume = sum(t.volume for t in recent if t.is_buy)
        sell_volume = sum(t.volume for t in recent if not t.is_buy)
        order_imbalance = safe_div(buy_volume - sell_volume, buy_volume + sell_volume, 0.0)
        direction = sign(order_imbalance, deadband=0.10)

        threshold_active = vpin >= self.toxic_threshold
        z_active = z >= self.z_threshold if len(hist) >= 10 else False
        active = direction != 0 and (threshold_active or z_active)
        confidence = clamp(max((vpin - 0.45) / 0.40, z / 3.0), 0.0, 1.0)
        strength = clamp(vpin, 0.0, 1.0)
        return SignalResult(
            signal_type=self.signal_type,
            instrument=symbol,
            direction=direction,
            confidence=confidence,
            strength=strength,
            active=active,
            lead_time="15-120 minutes",
            lead_time_minutes=15,
            source="trade_stream",
            details={
                "vpin": vpin,
                "vpin_z": z,
                "bucket_count": len(buckets),
                "order_imbalance": order_imbalance,
                "buy_volume_recent": buy_volume,
                "sell_volume_recent": sell_volume,
                "threshold_active": threshold_active,
                "z_active": z_active,
                "extreme_event": z >= 3.0,
            },
        )

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        out: List[SignalResult] = []
        for symbol in list(self.trades.keys()):
            if allowed is not None and symbol not in allowed:
                continue
            result = self.evaluate_symbol(symbol, append_history=False)
            if result is not None:
                out.append(result)
        return out


# ---------------------------------------------------------------------------
# SIGNAL 5: Entropy collapse + volatility squeeze detector
# ---------------------------------------------------------------------------


class VolatilitySqueezeDetector:
    """Bollinger-width, ATR-compression and entropy-collapse detector."""

    signal_type = "VOLATILITY_SQUEEZE"

    def __init__(self, maxlen: int = 300) -> None:
        self.bars: Dict[str, Deque[OHLCVBar]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update_bar(self, bar: OHLCVBar) -> None:
        self.bars[bar.symbol].append(bar)

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        results: List[SignalResult] = []
        for symbol, bar_deque in self.bars.items():
            if allowed is not None and symbol not in allowed:
                continue
            bars = list(bar_deque)
            if len(bars) < 30:
                continue
            closes = [b.close for b in bars]
            highs = [b.high for b in bars]
            lows = [b.low for b in bars]
            widths = bollinger_widths(closes, window=20)
            if not widths:
                continue
            current_bw = widths[-1]
            lookback_widths = widths[-min(120, len(widths)) :]
            min_bw = min(lookback_widths) if lookback_widths else current_bw
            bb_percentile = percentile_rank(lookback_widths, current_bw)
            bb_squeeze = current_bw <= min_bw * 1.15 or bb_percentile <= 10.0

            atr5 = atr(highs, lows, closes, 5)
            atr20 = atr(highs, lows, closes, 20)
            atr_ratio = safe_div(atr5, atr20, 1.0)
            atr_compression = atr_ratio <= 0.65

            entropy_recent = normalised_sign_entropy(closes[-20:])
            entropy_hist = [normalised_sign_entropy(closes[max(0, i - 20) : i]) for i in range(21, len(closes) + 1)]
            entropy_percentile = percentile_rank(entropy_hist, entropy_recent) if entropy_hist else 50.0
            entropy_collapse = entropy_recent <= 0.45 or entropy_percentile <= 15.0

            squeeze_score = 0.0
            if bb_squeeze:
                squeeze_score += 0.45
            if atr_compression:
                squeeze_score += 0.35
            if entropy_collapse:
                squeeze_score += 0.20
            # A Bollinger width sitting in the lowest decile is itself a valid
            # squeeze even when ATR/entropy lag by one or two bars.
            if bb_percentile <= 10.0:
                squeeze_score += 0.10
            squeeze_score = clamp(squeeze_score, 0.0, 1.0)
            active = squeeze_score >= 0.50
            results.append(
                SignalResult(
                    signal_type=self.signal_type,
                    instrument=symbol,
                    direction=0,
                    confidence=clamp(squeeze_score, 0.0, 1.0),
                    strength=clamp(squeeze_score, 0.0, 1.0),
                    active=active,
                    lead_time="1-72 hours",
                    lead_time_minutes=60,
                    source="ohlcv_bars",
                    details={
                        "bb_width": current_bw,
                        "bb_min_window": min_bw,
                        "bb_percentile": bb_percentile,
                        "bb_squeeze": bb_squeeze,
                        "atr5": atr5,
                        "atr20": atr20,
                        "atr_ratio": atr_ratio,
                        "atr_compression": atr_compression,
                        "entropy": entropy_recent,
                        "entropy_percentile": entropy_percentile,
                        "entropy_collapse": entropy_collapse,
                        "squeeze_score": squeeze_score,
                    },
                )
            )
        return results


# ---------------------------------------------------------------------------
# SIGNAL 6: Cross-market momentum divergence detector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrelationPair:
    a: str
    b: str
    instrument: str
    expected_corr: float
    name: str
    driver: str = "b"  # Which side is treated as fundamental anchor for direction.


DEFAULT_CORRELATION_PAIRS: Tuple[CorrelationPair, ...] = (
    CorrelationPair("XAUUSD", "REALYIELD", "XAUUSD", -0.80, "Gold-RealYield", driver="b"),
    CorrelationPair("AUDUSD", "HG", "AUDUSD", +0.75, "AUDUSD-Copper", driver="b"),
    CorrelationPair("USDJPY", "TNX", "USDJPY", +0.70, "USDJPY-10Y", driver="b"),
    CorrelationPair("XAGUSD", "XAUUSD", "XAGUSD", +0.85, "Silver-Gold", driver="b"),
)


class CorrelationDivergenceDetector:
    """Detect breakdowns in physically-linked market relationships."""

    signal_type = "CORRELATION_DIVERGENCE"

    def __init__(
        self,
        pairs: Sequence[CorrelationPair] = DEFAULT_CORRELATION_PAIRS,
        maxlen: int = 300,
    ) -> None:
        self.pairs = tuple(pairs)
        self.bars: Dict[str, Deque[OHLCVBar]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update_bar(self, bar: OHLCVBar) -> None:
        self.bars[bar.symbol].append(bar)

    def _closes(self, symbol: str) -> List[float]:
        return [b.close for b in self.bars.get(symbol, ())]

    @staticmethod
    def _reversion_direction(pair: CorrelationPair, a_ret: float, b_ret: float, corr_gap: float) -> int:
        # Instrument is normally `a`. Direction is where `a` should move to
        # restore the expected relationship to the driver (`b`).
        if pair.expected_corr > 0:
            # Same-direction relationship: if a lagged below b, long a; if a
            # outran b, short a.
            return 1 if a_ret < b_ret else -1
        # Inverse relationship: if a and b moved same way, a should revert the
        # opposite way of its latest move. If moves already oppose but correlation
        # still broke, use corr_gap sign as a softer reversion cue.
        if sign(a_ret) == sign(b_ret) and sign(a_ret) != 0:
            return -sign(a_ret)
        return sign(corr_gap)

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        results: List[SignalResult] = []
        for pair in self.pairs:
            if allowed is not None and pair.instrument not in allowed:
                continue
            a = self._closes(pair.a)
            b = self._closes(pair.b)
            n = min(len(a), len(b))
            if n < 30:
                continue
            a = a[-n:]
            b = b[-n:]
            window = min(21, n)
            curr_corr = correlation(a[-window:], b[-window:])
            corr_hist = rolling_correlations(a, b, window)
            corr_gap = pair.expected_corr - curr_corr
            # Avoid a zero-variance correlation history hiding a dramatic break.
            corr_z = safe_div(corr_gap, max(std(corr_hist), 0.10), 0.0)
            a_ret = safe_div(a[-1] - a[-5], abs(a[-5]), 0.0)
            b_ret = safe_div(b[-1] - b[-5], abs(b[-5]), 0.0)
            direction = self._reversion_direction(pair, a_ret, b_ret, corr_gap)
            diverged = abs(corr_gap) >= 0.55 or abs(corr_z) >= 1.50
            confidence = clamp(max(abs(corr_gap) / 1.5, abs(corr_z) / 4.0), 0.0, 1.0) if diverged else 0.0
            results.append(
                SignalResult(
                    signal_type=self.signal_type,
                    instrument=pair.instrument,
                    direction=direction if diverged else 0,
                    confidence=confidence,
                    strength=confidence,
                    active=diverged and direction != 0 and confidence >= 0.25,
                    lead_time="1-14 days",
                    lead_time_minutes=1440,
                    source=pair.name,
                    details={
                        "pair": pair.name,
                        "a": pair.a,
                        "b": pair.b,
                        "expected_corr": pair.expected_corr,
                        "current_corr": curr_corr,
                        "corr_gap": corr_gap,
                        "corr_z": corr_z,
                        "a_return_5": a_ret,
                        "b_return_5": b_ret,
                        "window": window,
                    },
                )
            )
        return results


# ---------------------------------------------------------------------------
# SIGNAL 7: Institutional footprint / COT velocity tracker
# ---------------------------------------------------------------------------


class InstitutionalFootprintTracker:
    """COT velocity/acceleration detector for institutional positioning."""

    signal_type = "COT_VELOCITY"

    def __init__(self, maxlen: int = 260) -> None:
        self.history: Dict[str, Deque[CotSnapshot]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update_snapshot(self, snapshot: CotSnapshot) -> None:
        self.history[snapshot.instrument].append(snapshot)

    @staticmethod
    def _accelerations(values: Sequence[float]) -> List[float]:
        if len(values) < 3:
            return []
        return [values[i] - 2.0 * values[i - 1] + values[i - 2] for i in range(2, len(values))]

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        results: List[SignalResult] = []
        for instrument, hist_deque in self.history.items():
            if allowed is not None and instrument not in allowed:
                continue
            hist = list(hist_deque)
            if len(hist) < 4:
                continue
            commercial = [s.commercial_net for s in hist]
            noncommercial = [s.noncommercial_net for s in hist]
            acc = self._accelerations(commercial)
            latest_acc = acc[-1]
            z = z_score(latest_acc, acc[:-1]) if len(acc) >= 3 else 0.0
            oi = max(abs(hist[-1].open_interest), 1.0)
            acc_oi = latest_acc / oi
            velocity_3 = safe_div(commercial[-1] - commercial[-3], 2.0, 0.0)

            # Commercials are treated as physical-informed hedgers; acceleration
            # in their net long exposure is bullish, acceleration lower is bearish.
            direction = sign(latest_acc)
            # Non-commercial momentum can confirm or conflict.
            noncom_velocity = noncommercial[-1] - noncommercial[-3] if len(noncommercial) >= 3 else 0.0
            noncom_confirm = sign(noncom_velocity) == direction and direction != 0

            magnitude = max(abs(z) / 3.0, abs(acc_oi) / 0.04)
            if noncom_confirm:
                magnitude *= 1.10
            confidence = clamp(magnitude, 0.0, 1.0)
            active = direction != 0 and (abs(z) >= 1.5 or abs(acc_oi) >= 0.015) and confidence >= 0.25
            results.append(
                SignalResult(
                    signal_type=self.signal_type,
                    instrument=instrument,
                    direction=direction if active else 0,
                    confidence=confidence if active else 0.0,
                    strength=confidence if active else 0.0,
                    active=active,
                    lead_time="3-21 days",
                    lead_time_minutes=4320,
                    source="cot_positioning",
                    details={
                        "commercial_latest": commercial[-1],
                        "commercial_velocity_3": velocity_3,
                        "commercial_acceleration": latest_acc,
                        "acceleration_z": z,
                        "acceleration_open_interest_ratio": acc_oi,
                        "noncommercial_velocity_3": noncom_velocity,
                        "noncommercial_confirm": noncom_confirm,
                    },
                )
            )
        return results


# ---------------------------------------------------------------------------
# SIGNAL 8: Physical-world supply/demand sensor fusion
# ---------------------------------------------------------------------------


class PhysicalWorldSensor:
    """Fuse cancelled warrants, inventory drawdowns, demand and real-world proxies."""

    signal_type = "PHYSICAL_WORLD"

    def __init__(self, maxlen: int = 260) -> None:
        self.history: Dict[str, Deque[PhysicalSnapshot]] = defaultdict(lambda: deque(maxlen=maxlen))

    def update_snapshot(self, snapshot: PhysicalSnapshot) -> None:
        self.history[snapshot.instrument].append(snapshot)

    def evaluate(self, instruments: Optional[Iterable[str]] = None) -> List[SignalResult]:
        allowed = set(instruments) if instruments is not None else None
        results: List[SignalResult] = []
        for instrument, hist_deque in self.history.items():
            if allowed is not None and instrument not in allowed:
                continue
            hist = list(hist_deque)
            if not hist:
                continue
            latest = hist[-1]
            components: List[Tuple[str, float, Dict[str, float]]] = []
            cw_ratio = latest.cancelled_warrant_ratio
            if cw_ratio >= 0.30:
                components.append(("major_cancelled_warrant_squeeze", +0.95, {"cw_ratio": cw_ratio}))
            elif cw_ratio >= 0.15:
                components.append(("cancelled_warrant_withdrawal", +0.60, {"cw_ratio": cw_ratio}))

            inventories = [s.inventory for s in hist if s.inventory is not None]
            if latest.inventory is not None and len(inventories) >= 5:
                inv_z = z_score(latest.inventory, inventories[:-1])
                # Inventory below normal = supply squeeze = bullish.
                if inv_z <= -1.5:
                    components.append(("inventory_drawdown", +clamp(abs(inv_z) / 3.0, 0.35, 1.0), {"inventory_z": inv_z}))
                elif inv_z >= 1.5:
                    components.append(("inventory_build", -clamp(abs(inv_z) / 3.0, 0.35, 1.0), {"inventory_z": inv_z}))

            if latest.production is not None and latest.demand is not None and latest.demand != 0:
                gap = (latest.demand - latest.production) / abs(latest.demand)
                if gap >= 0.05:
                    components.append(("physical_demand_exceeds_production", +clamp(gap / 0.20, 0.25, 0.90), {"production_gap": gap}))
                elif gap <= -0.05:
                    components.append(("production_exceeds_demand", -clamp(abs(gap) / 0.20, 0.25, 0.90), {"production_gap": gap}))

            if latest.port_congestion_index is not None:
                pc = latest.port_congestion_index
                if pc >= 2.0:
                    components.append(("port_congestion_supply_delay", +clamp(pc / 5.0, 0.25, 0.70), {"port_congestion_index": pc}))
            if latest.electricity_demand_index is not None:
                ed = latest.electricity_demand_index
                if ed >= 1.5:
                    components.append(("industrial_power_demand_rising", +clamp(ed / 4.0, 0.20, 0.60), {"electricity_demand_index": ed}))
                elif ed <= -1.5:
                    components.append(("industrial_power_demand_falling", -clamp(abs(ed) / 4.0, 0.20, 0.60), {"electricity_demand_index": ed}))
            if latest.google_trends_index is not None:
                gt = latest.google_trends_index
                if gt >= 2.0:
                    components.append(("retail_search_demand_spike", +clamp(gt / 5.0, 0.20, 0.50), {"google_trends_index": gt}))

            signed = sum(c[1] for c in components)
            direction = sign(signed, deadband=0.15)
            confidence = clamp(abs(signed) / 2.6, 0.0, 1.0)
            active = direction != 0 and confidence >= 0.25
            if components or allowed is not None:
                results.append(
                    SignalResult(
                        signal_type=self.signal_type,
                        instrument=instrument,
                        direction=direction,
                        confidence=confidence,
                        strength=clamp(abs(signed), 0.0, 1.0),
                        active=active,
                        lead_time="1-21 days",
                        lead_time_minutes=1440,
                        source="physical_sensors",
                        details={
                            "cancelled_warrant_ratio": cw_ratio,
                            "components": components,
                        },
                    )
                )
        return results


__all__ = [
    "LeadPair",
    "DEFAULT_LEAD_PAIRS",
    "CrossAssetLeadDetector",
    "OptionsFlowAnomalyDetector",
    "DarkPoolBlockTradeDetector",
    "VPINCalculator",
    "VolatilitySqueezeDetector",
    "CorrelationPair",
    "DEFAULT_CORRELATION_PAIRS",
    "CorrelationDivergenceDetector",
    "InstitutionalFootprintTracker",
    "PhysicalWorldSensor",
]
