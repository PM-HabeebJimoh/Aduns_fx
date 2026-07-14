"""Risk controls and position sizing for HYDRA-PRIME decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

from .math_utils import clamp
from .models import PositionPlan, utcnow


@dataclass(frozen=True)
class RiskLimits:
    """Hard limits used by the engine before a signal is allowed to fire."""

    max_trade_risk_pct: float = 2.0
    max_leverage: float = 5.0
    hard_pause_drawdown_pct: float = 15.0
    max_portfolio_drawdown_pct: float = 20.0
    max_daily_loss_pct: float = 5.0
    reward_to_risk: float = 1.5


@dataclass
class RiskManager:
    """Stateful risk manager with drawdown and daily-loss kill switches."""

    capital: float = 10_000.0
    limits: RiskLimits = field(default_factory=RiskLimits)
    current_equity: Optional[float] = None
    peak_equity: Optional[float] = None
    daily_start_equity: Optional[float] = None
    current_day: Optional[date] = None
    realised_pnl: float = 0.0
    trade_log: List[Dict[str, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.current_equity is None:
            self.current_equity = float(self.capital)
        if self.peak_equity is None:
            self.peak_equity = float(self.current_equity)
        if self.daily_start_equity is None:
            self.daily_start_equity = float(self.current_equity)
        if self.current_day is None:
            self.current_day = utcnow().date()

    @property
    def drawdown_pct(self) -> float:
        if not self.peak_equity or self.peak_equity <= 0:
            return 0.0
        return max(0.0, 100.0 * (self.peak_equity - self.current_equity) / self.peak_equity)

    @property
    def daily_pnl_pct(self) -> float:
        if not self.daily_start_equity or self.daily_start_equity <= 0:
            return 0.0
        return 100.0 * (self.current_equity - self.daily_start_equity) / self.daily_start_equity

    def roll_day_if_needed(self, now: Optional[datetime] = None) -> None:
        today = (now or utcnow()).date()
        if self.current_day != today:
            self.current_day = today
            self.daily_start_equity = float(self.current_equity)

    def can_trade(self) -> tuple[bool, str]:
        self.roll_day_if_needed()
        if self.drawdown_pct >= self.limits.hard_pause_drawdown_pct:
            return False, f"Hard pause: drawdown {self.drawdown_pct:.2f}% >= {self.limits.hard_pause_drawdown_pct:.2f}%"
        if self.daily_pnl_pct <= -self.limits.max_daily_loss_pct:
            return False, f"Daily loss stop: {self.daily_pnl_pct:.2f}% <= -{self.limits.max_daily_loss_pct:.2f}%"
        return True, ""

    def record_pnl(self, pnl: float, metadata: Optional[Dict[str, float]] = None) -> None:
        self.roll_day_if_needed()
        self.realised_pnl += float(pnl)
        self.current_equity = float(self.current_equity) + float(pnl)
        self.peak_equity = max(float(self.peak_equity), float(self.current_equity))
        entry: Dict[str, float] = {"pnl": float(pnl), "equity": float(self.current_equity)}
        if metadata:
            entry.update(metadata)
        self.trade_log.append(entry)

    def _sizing_plan(
        self,
        instrument: str,
        direction: int,
        score: float,
        reference_price: Optional[float] = None,
        reason: str = "",
    ) -> PositionPlan:
        if direction == 0 or score < 70:
            return PositionPlan(
                instrument=instrument,
                direction=direction,
                leverage=0.0,
                risk_pct=0.0,
                stop_loss_pct=0.0,
                take_profit_pct=0.0,
                max_loss_dollars=0.0,
                notional_size=0.0,
                units=None,
                blocked=True,
                reason=reason or "Below fire threshold / neutral direction",
            )

        if score >= 90:
            leverage = 5.0
            risk_pct = 2.0
        elif score >= 80:
            leverage = 3.0
            risk_pct = 1.5
        else:
            leverage = 2.0
            risk_pct = 1.0

        leverage = min(leverage, self.limits.max_leverage)
        risk_pct = min(risk_pct, self.limits.max_trade_risk_pct)
        equity = float(self.current_equity)
        max_loss = equity * risk_pct / 100.0
        stop_loss_pct = risk_pct / max(leverage, 1e-12)
        take_profit_pct = stop_loss_pct * self.limits.reward_to_risk
        notional = equity * leverage
        units = notional / reference_price if reference_price and reference_price > 0 else None
        return PositionPlan(
            instrument=instrument,
            direction=direction,
            leverage=leverage,
            risk_pct=risk_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_loss_dollars=round(max_loss, 2),
            notional_size=round(notional, 2),
            units=units,
            blocked=False,
            reason=reason,
        )

    def advisory_position_plan(
        self,
        instrument: str,
        direction: int,
        score: float,
        reference_price: Optional[float] = None,
    ) -> PositionPlan:
        """Return suggested trade parameters for an alert without executing.

        This is advisory sizing only. It does not check broker state, route an
        order, reserve margin, or create a fill. The alert can include leverage,
        notional, risk %, stop, target, and max loss while execution remains
        completely external to HYDRA-PRIME.
        """

        return self._sizing_plan(
            instrument,
            direction,
            score,
            reference_price,
            reason="Advisory only: HYDRA-PRIME does not execute trades",
        )

    def position_plan(
        self,
        instrument: str,
        direction: int,
        score: float,
        reference_price: Optional[float] = None,
    ) -> PositionPlan:
        allowed, reason = self.can_trade()
        if not allowed:
            return PositionPlan(
                instrument=instrument,
                direction=direction,
                leverage=0.0,
                risk_pct=0.0,
                stop_loss_pct=0.0,
                take_profit_pct=0.0,
                max_loss_dollars=0.0,
                notional_size=0.0,
                units=None,
                blocked=True,
                reason=reason,
            )
        return self._sizing_plan(instrument, direction, score, reference_price)

    def portfolio_status(self) -> Dict[str, float | str]:
        allowed, reason = self.can_trade()
        return {
            "capital": float(self.capital),
            "current_equity": float(self.current_equity),
            "peak_equity": float(self.peak_equity),
            "drawdown_pct": self.drawdown_pct,
            "daily_pnl_pct": self.daily_pnl_pct,
            "realised_pnl": self.realised_pnl,
            "can_trade": str(allowed),
            "reason": reason,
        }
