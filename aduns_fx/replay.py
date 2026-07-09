"""Historical opportunity replay from verified HYDRA feed CSVs.

This is not trade simulation. It replays already-verified real feed rows through
HYDRA's detectors and records opportunity alerts that would have been emitted by
engine evaluation checkpoints. No fills, P&L, slippage, or order assumptions are
created.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .engine import HydraPrimeEngine
from .models import (
    CotSnapshot,
    DarkPoolSnapshot,
    OHLCVBar,
    OptionSnapshot,
    PhysicalSnapshot,
    PriceTick,
    TradeTick,
)


@dataclass(frozen=True)
class ReplayEvent:
    timestamp: datetime
    feed_name: str
    row: Dict[str, str]


@dataclass
class OpportunityReplaySummary:
    start: str
    end: str
    events_loaded: int
    evaluation_days: int
    alerts_count: int
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_ts(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_bool(value: str | bool | None) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "y", "buy"}


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_date_bound(value: str, end: bool = False) -> datetime:
    d = datetime.fromisoformat(value).date()
    if end:
        return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


class OpportunityReplayRunner:
    """Replay normalized HYDRA CSV feeds through the opportunity engine."""

    def __init__(
        self,
        data_dir: str | Path,
        manifest: Dict[str, Any],
        start: str,
        end: str,
        capital: float = 10_000.0,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.manifest = manifest
        self.start_raw = start
        self.end_raw = end
        self.start = parse_date_bound(start)
        self.end = parse_date_bound(end, end=True)
        self.engine = HydraPrimeEngine(capital=capital)

    def _feed_paths(self) -> Dict[str, Path]:
        out: Dict[str, Path] = {}
        for entry in self.manifest.get("feeds", []):
            if not isinstance(entry, dict) or "name" not in entry or "path" not in entry:
                continue
            out[entry["name"]] = self.data_dir / str(entry["path"])
        return out

    def load_events(self) -> List[ReplayEvent]:
        events: List[ReplayEvent] = []
        for feed_name, path in self._feed_paths().items():
            if not path.exists() or path.suffix.lower() != ".csv":
                continue
            with path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    ts_raw = row.get("timestamp")
                    if not ts_raw:
                        continue
                    try:
                        ts = parse_ts(ts_raw)
                    except Exception:
                        continue
                    if self.start <= ts <= self.end:
                        events.append(ReplayEvent(ts, feed_name, dict(row)))
        events.sort(key=lambda e: (e.timestamp, e.feed_name))
        return events

    def ingest_event(self, event: ReplayEvent) -> None:
        row = event.row
        feed = event.feed_name
        if feed == "cross_asset_price_ticks":
            self.engine.ingest_price(PriceTick(row["symbol"], parse_float(row.get("price")), event.timestamp))
        elif feed == "vpin_trade_ticks":
            self.engine.ingest_trade(
                TradeTick(
                    symbol=row["symbol"],
                    price=parse_float(row.get("price")),
                    volume=parse_float(row.get("volume")),
                    is_buy=parse_bool(row.get("is_buy")),
                    timestamp=event.timestamp,
                )
            )
        elif feed == "ohlcv_intraday_bars":
            self.engine.ingest_bar(
                OHLCVBar(
                    symbol=row["symbol"],
                    timestamp=event.timestamp,
                    open=parse_float(row.get("open")),
                    high=parse_float(row.get("high")),
                    low=parse_float(row.get("low")),
                    close=parse_float(row.get("close")),
                    volume=parse_float(row.get("volume")),
                )
            )
        elif feed == "options_flow_snapshots":
            self.engine.ingest_options(
                OptionSnapshot(
                    instrument=row["instrument"],
                    call_volume=parse_float(row.get("call_volume")),
                    put_volume=parse_float(row.get("put_volume")),
                    otm_call_volume=parse_float(row.get("otm_call_volume")),
                    otm_put_volume=parse_float(row.get("otm_put_volume")),
                    timestamp=event.timestamp,
                )
            )
        elif feed == "dark_pool_block_prints":
            self.engine.ingest_dark_pool(
                DarkPoolSnapshot(
                    instrument=row["instrument"],
                    dark_pool_volume=parse_float(row.get("dark_pool_volume")),
                    total_volume=parse_float(row.get("total_volume")),
                    short_volume=parse_float(row.get("short_volume")),
                    timestamp=event.timestamp,
                )
            )
        elif feed == "cot_positioning":
            self.engine.ingest_cot(
                CotSnapshot(
                    instrument=row["instrument"],
                    commercial_net=parse_float(row.get("commercial_net")),
                    noncommercial_net=parse_float(row.get("noncommercial_net")),
                    open_interest=parse_float(row.get("open_interest"), 1.0),
                    timestamp=event.timestamp,
                )
            )
        elif feed == "physical_inventory_sensors":
            metadata: Dict[str, Any] = {}
            if row.get("metadata"):
                try:
                    metadata = json.loads(row.get("metadata", "{}"))
                except json.JSONDecodeError:
                    metadata = {"raw_metadata": row.get("metadata")}
            self.engine.ingest_physical(
                PhysicalSnapshot(
                    instrument=row["instrument"],
                    total_warrants=parse_float(row.get("total_warrants")),
                    cancelled_warrants=parse_float(row.get("cancelled_warrants")),
                    inventory=parse_float(row.get("inventory")) if row.get("inventory") else None,
                    production=parse_float(row.get("production")) if row.get("production") else None,
                    demand=parse_float(row.get("demand")) if row.get("demand") else None,
                    port_congestion_index=parse_float(row.get("port_congestion_index")) if row.get("port_congestion_index") else None,
                    electricity_demand_index=parse_float(row.get("electricity_demand_index")) if row.get("electricity_demand_index") else None,
                    google_trends_index=parse_float(row.get("google_trends_index")) if row.get("google_trends_index") else None,
                    timestamp=event.timestamp,
                    metadata=metadata,
                )
            )

    def _record_alerts(self, when: datetime) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for decision in self.engine.alerts():
            out.append(
                {
                    "evaluation_timestamp": when.isoformat().replace("+00:00", "Z"),
                    "instrument": decision.instrument,
                    "direction": decision.direction_label,
                    "score": decision.pre_move_score,
                    "n_agreeing": decision.n_agreeing,
                    "lead_time_estimate": decision.lead_time_estimate,
                    "advisory_position": asdict(decision.position),
                    "signal_types": sorted({vote.signal_type for vote in decision.votes}),
                }
            )
        return out

    def run(self) -> OpportunityReplaySummary:
        events = self.load_events()
        alerts: List[Dict[str, Any]] = []
        evaluation_days = 0
        current_day: Optional[date] = None
        last_ts = self.start
        for event in events:
            if current_day is None:
                current_day = event.timestamp.date()
            elif event.timestamp.date() != current_day:
                evaluation_days += 1
                alerts.extend(self._record_alerts(last_ts))
                current_day = event.timestamp.date()
            self.ingest_event(event)
            last_ts = event.timestamp
        if events:
            evaluation_days += 1
            alerts.extend(self._record_alerts(last_ts))
        return OpportunityReplaySummary(
            start=self.start_raw,
            end=self.end_raw,
            events_loaded=len(events),
            evaluation_days=evaluation_days,
            alerts_count=len(alerts),
            alerts=alerts,
            notes=[
                "Opportunity replay only: no trade execution, no fills, no P&L, no slippage assumptions.",
                "Replay uses only rows present in verified manifest CSV feeds.",
            ],
        )
