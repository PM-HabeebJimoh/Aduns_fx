"""Core data models for HYDRA-PRIME.

The models are intentionally small and serialisable so they can be fed from
live APIs, CSV files, fixtures, broker streams, or synthetic tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, List, Optional


class Direction(IntEnum):
    """Directional convention used by every signal and decision."""

    SHORT = -1
    NEUTRAL = 0
    LONG = 1


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def direction_label(direction: int) -> str:
    if direction > 0:
        return "LONG"
    if direction < 0:
        return "SHORT"
    return "NEUTRAL"


@dataclass(frozen=True)
class PriceTick:
    symbol: str
    price: float
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class TradeTick:
    symbol: str
    price: float
    volume: float
    is_buy: Optional[bool] = None
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class OHLCVBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class OptionSnapshot:
    """Options-flow snapshot for one underlying/instrument.

    Volumes can be daily totals, rolling window totals, or exchange-provided
    bucket totals as long as the same convention is used through time.
    Implied vol fields are in volatility points, e.g. 22.5 not 0.225.
    """

    instrument: str
    call_volume: float
    put_volume: float
    otm_call_volume: float = 0.0
    otm_put_volume: float = 0.0
    iv_call_25d: Optional[float] = None
    iv_put_25d: Optional[float] = None
    underlying_price: Optional[float] = None
    timestamp: datetime = field(default_factory=utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def put_call_ratio(self) -> float:
        if self.call_volume <= 0:
            return float("inf") if self.put_volume > 0 else 1.0
        return self.put_volume / self.call_volume

    @property
    def call_put_ratio(self) -> float:
        if self.put_volume <= 0:
            return float("inf") if self.call_volume > 0 else 1.0
        return self.call_volume / self.put_volume

    @property
    def risk_reversal_25d(self) -> Optional[float]:
        if self.iv_call_25d is None or self.iv_put_25d is None:
            return None
        return self.iv_call_25d - self.iv_put_25d


@dataclass(frozen=True)
class DarkPoolSnapshot:
    """Dark-pool/block/short-volume snapshot.

    `block_buy_ratio` is optional because many public feeds only report volume,
    not aggressor side. When supplied, 1.0 means all blocks were buyer-initiated,
    0.0 means all seller-initiated.
    """

    instrument: str
    dark_pool_volume: float
    total_volume: float
    short_volume: float = 0.0
    close: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    block_buy_ratio: Optional[float] = None
    timestamp: datetime = field(default_factory=utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def dark_pool_ratio(self) -> float:
        if self.total_volume <= 0:
            return 0.0
        return self.dark_pool_volume / self.total_volume

    @property
    def short_ratio(self) -> float:
        if self.total_volume <= 0:
            return 0.0
        return self.short_volume / self.total_volume


@dataclass(frozen=True)
class CotSnapshot:
    """Commitment-of-Traders positioning snapshot.

    Values should be net positions. Commercials are treated as the physical
    hedger footprint; non-commercials represent managed/speculative money.
    """

    instrument: str
    commercial_net: float
    noncommercial_net: float = 0.0
    open_interest: float = 1.0
    timestamp: datetime = field(default_factory=utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PhysicalSnapshot:
    """Physical-world supply/demand snapshot.

    All fields are optional except `instrument`; detector logic uses whatever
    physical sensors are available and ignores missing/zero denominators.
    `port_congestion_index`, `electricity_demand_index`, and
    `google_trends_index` are expected to be z-score-like normalised readings
    when available.
    """

    instrument: str
    total_warrants: float = 0.0
    cancelled_warrants: float = 0.0
    inventory: Optional[float] = None
    production: Optional[float] = None
    demand: Optional[float] = None
    port_congestion_index: Optional[float] = None
    electricity_demand_index: Optional[float] = None
    google_trends_index: Optional[float] = None
    timestamp: datetime = field(default_factory=utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def cancelled_warrant_ratio(self) -> float:
        if self.total_warrants <= 0:
            return 0.0
        return self.cancelled_warrants / self.total_warrants


@dataclass(frozen=True)
class SignalResult:
    """One detector's directional evidence for one instrument."""

    signal_type: str
    instrument: str
    direction: int = 0
    confidence: float = 0.0
    strength: float = 0.0
    active: bool = False
    lead_time: str = "Unknown"
    lead_time_minutes: Optional[float] = None
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def signed_confidence(self) -> float:
        return float(self.direction) * self.confidence

    @property
    def label(self) -> str:
        return direction_label(self.direction)


@dataclass(frozen=True)
class PositionPlan:
    instrument: str
    direction: int
    leverage: float
    risk_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_loss_dollars: float
    notional_size: float
    units: Optional[float] = None
    blocked: bool = False
    reason: str = ""


@dataclass(frozen=True)
class Decision:
    instrument: str
    direction: int
    pre_move_score: float
    fire: bool
    n_signals: int
    n_independent: int
    n_agreeing: int
    bull_score: float
    bear_score: float
    lead_time_estimate: str
    position: PositionPlan
    votes: List[SignalResult] = field(default_factory=list)
    squeeze_active: bool = False
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def direction_label(self) -> str:
        return direction_label(self.direction)
