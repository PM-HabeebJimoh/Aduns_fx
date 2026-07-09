"""Human-readable opportunity-alert formatting."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from .models import Decision, SignalResult


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if is_dataclass(obj):
        return asdict(obj)
    return str(obj)


def decision_to_json(decision: Decision, indent: int = 2) -> str:
    return json.dumps(asdict(decision), default=_json_default, indent=indent)


def format_signal_vote(vote: SignalResult) -> str:
    label = "BULL" if vote.direction > 0 else "BEAR" if vote.direction < 0 else "NEUTRAL"
    return f"  • {vote.signal_type}: {label} ({vote.confidence:.0%} conf, {vote.lead_time})"


def format_pre_move_signal(decision: Decision, capital: float | None = None) -> str:
    """Format one opportunity decision for Telegram/console/log delivery.

    HYDRA-PRIME does not execute, but the alert includes advisory execution
    parameters: leverage, notional, risk %, stop, take profit, max loss and units
    when a reference price is available.
    """

    inst = decision.instrument
    score = decision.pre_move_score
    if not decision.fire:
        reason = "; ".join(decision.warnings) if decision.warnings else decision.details.get("reason", "No opportunity")
        return f"⬜ {inst}: Score={score:.0f}/100 — No opportunity detected. {reason}"

    direction_word = "LONG" if decision.direction > 0 else "SHORT"
    bias_word = "LONG-BIAS" if decision.direction > 0 else "SHORT-BIAS"
    direction_icon = "🟢" if decision.direction > 0 else "🔴"
    pos = decision.position
    votes = "\n".join(format_signal_vote(v) for v in decision.votes)
    units_line = f"  Units:       {pos.units:,.6f}\n" if pos.units is not None else ""
    cap = capital if capital is not None else (pos.notional_size / max(pos.leverage, 1.0) if pos.leverage else 0.0)

    return (
        "🚨 PRE-MOVEMENT OPPORTUNITY DETECTED\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {inst} | {direction_icon} {bias_word}\n"
        f"🎯 Opportunity score: {score:.0f}/100\n"
        f"⏰ Expected movement window: {decision.lead_time_estimate}\n"
        f"🔢 Agreeing independent signals: {decision.n_agreeing}\n"
        f"{'⚡ VOLATILITY SQUEEZE ACTIVE' if decision.squeeze_active else ''}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📡 WHY IT FIRED:\n"
        f"{votes}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 ADVISORY EXECUTION PARAMETERS:\n"
        f"  Direction:   {direction_word}\n"
        f"  Leverage:    {pos.leverage:.1f}x\n"
        f"  Notional:    ${pos.notional_size:,.0f}\n"
        f"  Risk:        {pos.risk_pct:.1f}%\n"
        f"  Max Loss:    ${pos.max_loss_dollars:,.0f}\n"
        f"  Stop Loss:   {pos.stop_loss_pct:.2f}%\n"
        f"  Take Profit: {pos.take_profit_pct:.2f}%\n"
        f"{units_line}"
        f"  Capital Ref: ${cap:,.0f}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ OUTPUT MODE:\n"
        "  Opportunity alert + advisory trade parameters\n"
        "  No broker execution\n"
        "  No order routing\n"
        "  No simulated fills\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Decision-support alert only. HYDRA-PRIME does not execute; use your own execution and risk process if you choose to act."
    )
