"""Strict real-data opportunity-replay audit runner for HYDRA-PRIME.

HYDRA-PRIME is now explicitly an opportunity-alert system. It does not place
trades, route orders, simulate fills, or require broker execution ledgers.

This runner verifies that every signal family has a real archived data feed for
the requested period. If anything is missing, it produces a BLOCKED report
instead of inventing opportunity statistics from incomplete or simulated data.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import utcnow
from .replay import OpportunityReplayRunner


ALLOWED_REALTIME_CAPTURE_MODES = {
    "realtime_archive",
    "real_time_archive",
    "live_capture_archive",
    "broker_realtime_archive",
    "exchange_realtime_archive",
    "vendor_realtime_archive",
    # Free replacement modes. These are accepted only because the user explicitly
    # requested public/free replacements for blocked original feeds. Reports keep
    # provenance labels so delayed/proxy sources are not misrepresented.
    "free_public_replacement",
    "official_delayed_archive",
    "public_historical_archive",
    "public_proxy_archive",
}

DISALLOWED_SOURCE_WORDS = {
    "demo",
    "synthetic",
    "simulated",
    "simulation",
    "mock",
    "sample",
    "fixture",
    "test",
    "generated",
    "theoretical",
}


@dataclass(frozen=True)
class RequiredFeed:
    name: str
    purpose: str
    min_granularity: str
    required_columns: Tuple[str, ...]
    why_required: str


REQUIRED_FEEDS: Tuple[RequiredFeed, ...] = (
    RequiredFeed(
        name="cross_asset_price_ticks",
        purpose="Cross-asset temporal leads",
        min_granularity="tick or <=1 minute archived real-time bars",
        required_columns=("timestamp", "symbol", "price"),
        why_required="Lead/lag detection cannot be reconstructed from daily data.",
    ),
    RequiredFeed(
        name="vpin_trade_ticks",
        purpose="VPIN/order-flow toxicity",
        min_granularity="trade tick archive",
        required_columns=("timestamp", "symbol", "price", "volume", "is_buy"),
        why_required="VPIN requires real trade sequence, volume buckets, and side classification/inference.",
    ),
    RequiredFeed(
        name="ohlcv_intraday_bars",
        purpose="Volatility squeeze and opportunity context",
        min_granularity="<=1 minute archived real-time OHLCV bars",
        required_columns=("timestamp", "symbol", "open", "high", "low", "close", "volume"),
        why_required="Squeeze and day/month opportunity replay need intraday bars.",
    ),
    RequiredFeed(
        name="options_flow_snapshots",
        purpose="Options-flow anomaly detector",
        min_granularity="archived snapshots or exchange option trades/open-interest by timestamp",
        required_columns=("timestamp", "instrument", "call_volume", "put_volume"),
        why_required="Options flow cannot be truthfully replaced by underlying OHLC data.",
    ),
    RequiredFeed(
        name="dark_pool_block_prints",
        purpose="Dark-pool/block footprint detector",
        min_granularity="official/vendor timestamped prints or daily regulatory file as published",
        required_columns=("timestamp", "instrument", "dark_pool_volume", "total_volume"),
        why_required="Institutional block/dark-pool footprints are a separate data source.",
    ),
    RequiredFeed(
        name="cot_positioning",
        purpose="Institutional COT velocity",
        min_granularity="weekly official COT archive",
        required_columns=("timestamp", "instrument", "commercial_net", "open_interest"),
        why_required="COT velocity cannot be inferred from price.",
    ),
    RequiredFeed(
        name="physical_inventory_sensors",
        purpose="Physical supply/demand sensors",
        min_granularity="official/vendor historical physical reports",
        required_columns=("timestamp", "instrument"),
        why_required="Cancelled warrants/inventory/production/demand are exogenous physical signals.",
    ),
)


@dataclass
class FeedAudit:
    name: str
    purpose: str
    status: str
    reason: str
    path: Optional[str] = None
    source: Optional[str] = None
    capture_mode: Optional[str] = None
    rows: int = 0
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    required_columns: Tuple[str, ...] = field(default_factory=tuple)
    missing_columns: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class BacktestAudit:
    requested_start: str
    requested_end: str
    data_dir: str
    strict_realtime_only: bool
    status: str
    generated_at: str
    blockers: List[str] = field(default_factory=list)
    feed_audits: List[FeedAudit] = field(default_factory=list)
    opportunity_replay: Optional[Dict[str, Any]] = None
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def _parse_date_or_datetime(value: str, end_of_day: bool = False) -> datetime:
    value = value.strip()
    if "T" in value or " " in value:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    d = datetime.fromisoformat(value).date()
    return datetime.combine(d, time.max if end_of_day else time.min, tzinfo=timezone.utc)


def _string_has_disallowed_source_word(value: str) -> Optional[str]:
    lower = value.lower()
    for word in sorted(DISALLOWED_SOURCE_WORDS):
        if word in lower:
            return word
    return None


def _read_csv_metadata(path: Path, timestamp_column: str = "timestamp") -> tuple[int, Optional[str], Optional[str], List[str]]:
    rows = 0
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        for row in reader:
            rows += 1
            ts = row.get(timestamp_column)
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
    return rows, first_ts, last_ts, columns


class StrictRealDataBacktester:
    """Provenance-gated opportunity replay auditor.

    It refuses to invent missing market data and it contains no execution/fill
    analysis. If the feed audit passes, the output is permission to run signal
    replay, not trading performance.
    """

    def __init__(
        self,
        data_dir: str | Path,
        start: str,
        end: str,
        strict_realtime_only: bool = True,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.start_raw = start
        self.end_raw = end
        self.start = _parse_date_or_datetime(start)
        self.end = _parse_date_or_datetime(end, end_of_day=True)
        self.strict_realtime_only = strict_realtime_only

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.json"

    def _load_manifest(self) -> Optional[Dict[str, Any]]:
        if not self.manifest_path.exists():
            return None
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _feed_entries(manifest: Dict[str, Any], feed_name: str) -> List[Dict[str, Any]]:
        entries = manifest.get("feeds", [])
        if not isinstance(entries, list):
            return []
        return [e for e in entries if isinstance(e, dict) and e.get("name") == feed_name]

    def _audit_required_feed(self, required: RequiredFeed, manifest: Optional[Dict[str, Any]]) -> FeedAudit:
        if manifest is None:
            return FeedAudit(
                name=required.name,
                purpose=required.purpose,
                status="MISSING",
                reason="No manifest.json was found, so no real-time provenance can be verified.",
                required_columns=required.required_columns,
            )

        entries = self._feed_entries(manifest, required.name)
        if not entries:
            replacement_policy = manifest.get("replacement_policy")
            if replacement_policy:
                reason = (
                    "Free/public replacement mode is enabled, but no normalized real-data CSV "
                    f"was produced for this feed. Run `acquire-replacements` on a network that can reach "
                    f"the replacement sources. {required.why_required}"
                )
                status = "MISSING_REPLACEMENT_OUTPUT"
            else:
                reason = f"Required feed is absent from manifest. {required.why_required}"
                status = "MISSING"
            return FeedAudit(
                name=required.name,
                purpose=required.purpose,
                status=status,
                reason=reason,
                required_columns=required.required_columns,
            )

        entry = entries[0]
        source = str(entry.get("source", ""))
        capture_mode = str(entry.get("capture_mode", ""))
        path_value = entry.get("path")
        audit = FeedAudit(
            name=required.name,
            purpose=required.purpose,
            status="PENDING",
            reason="",
            path=str(path_value) if path_value else None,
            source=source or None,
            capture_mode=capture_mode or None,
            required_columns=required.required_columns,
        )

        if not path_value:
            audit.status = "INVALID"
            audit.reason = "Manifest entry has no path."
            return audit

        suspect_word = _string_has_disallowed_source_word(" ".join([source, str(path_value), str(entry.get("description", ""))]))
        if entry.get("synthetic") is True or entry.get("simulated") is True or suspect_word:
            audit.status = "REJECTED"
            audit.reason = f"Feed is marked or named as non-real data ({suspect_word or 'synthetic/simulated flag'})."
            return audit

        if self.strict_realtime_only and capture_mode.lower() not in ALLOWED_REALTIME_CAPTURE_MODES:
            audit.status = "REJECTED"
            audit.reason = (
                f"capture_mode='{capture_mode}' is not an archived real-time capture mode. "
                "Historical/delayed/API-reconstructed data is not accepted under the strict constraint."
            )
            return audit

        path = (self.data_dir / str(path_value)).resolve()
        try:
            path.relative_to(self.data_dir.resolve())
        except ValueError:
            audit.status = "REJECTED"
            audit.reason = "Feed path escapes the data directory."
            return audit

        if not path.exists():
            audit.status = "MISSING"
            audit.reason = f"Manifest path does not exist: {path_value}"
            return audit
        if path.stat().st_size == 0:
            audit.status = "INVALID"
            audit.reason = "Feed file is empty."
            return audit
        if path.suffix.lower() != ".csv":
            audit.status = "REJECTED"
            audit.reason = "Only CSV archives are currently auditable by the strict runner."
            return audit

        try:
            rows, first_ts, last_ts, columns = _read_csv_metadata(path)
        except Exception as exc:
            audit.status = "INVALID"
            audit.reason = f"Could not read CSV metadata: {exc}"
            return audit

        audit.rows = rows
        audit.first_timestamp = first_ts
        audit.last_timestamp = last_ts
        missing = tuple(c for c in required.required_columns if c not in columns)
        audit.missing_columns = missing
        if rows == 0:
            audit.status = "INVALID"
            audit.reason = "CSV contains zero data rows."
            return audit
        if missing:
            audit.status = "INVALID"
            audit.reason = "CSV is missing required columns: " + ", ".join(missing)
            return audit

        if first_ts and last_ts:
            try:
                first_dt = _parse_date_or_datetime(first_ts)
                last_dt = _parse_date_or_datetime(last_ts, end_of_day=True)
                if first_dt > self.start:
                    audit.status = "INVALID"
                    audit.reason = f"Feed starts after requested start: {first_ts} > {self.start_raw}"
                    return audit
                if last_dt < self.end:
                    audit.status = "INVALID"
                    audit.reason = f"Feed ends before requested end: {last_ts} < {self.end_raw}"
                    return audit
            except Exception:
                audit.status = "INVALID"
                audit.reason = "Timestamp coverage could not be parsed/verified."
                return audit

        audit.status = "OK"
        audit.reason = "Provenance, columns, non-empty data, and requested date coverage verified."
        return audit

    def audit(self) -> BacktestAudit:
        blockers: List[str] = []
        manifest: Optional[Dict[str, Any]] = None

        if not self.data_dir.exists():
            blockers.append(f"Data directory does not exist: {self.data_dir}")
        elif not self.data_dir.is_dir():
            blockers.append(f"Data path is not a directory: {self.data_dir}")
        else:
            manifest = self._load_manifest()
            if manifest is None:
                blockers.append(f"Missing manifest: {self.manifest_path}")

        feed_audits = [self._audit_required_feed(feed, manifest) for feed in REQUIRED_FEEDS]
        for audit in feed_audits:
            if audit.status != "OK":
                blockers.append(f"{audit.name}: {audit.reason}")

        status = "OK" if not blockers else "BLOCKED"
        note = (
            "Strict opportunity replay feed audit passed. Execution is disabled; no P&L/ROI/fill analysis is produced."
            if status == "OK"
            else "No opportunity replay was produced because doing so would require missing data or simulated assumptions."
        )
        return BacktestAudit(
            requested_start=self.start_raw,
            requested_end=self.end_raw,
            data_dir=str(self.data_dir),
            strict_realtime_only=self.strict_realtime_only,
            status=status,
            generated_at=utcnow().isoformat(),
            blockers=blockers,
            feed_audits=feed_audits,
            note=note,
        )

    def run(self) -> BacktestAudit:
        audit = self.audit()
        if audit.status != "OK":
            return audit
        manifest = self._load_manifest() or {}
        replay = OpportunityReplayRunner(
            data_dir=self.data_dir,
            manifest=manifest,
            start=self.start_raw,
            end=self.end_raw,
        ).run()
        audit.opportunity_replay = replay.to_dict()
        audit.note = (
            "Strict opportunity replay completed from verified manifest CSV feeds. "
            "Execution is disabled; no P&L/ROI/fill analysis is produced."
        )
        return audit

    def write_report(self, report_dir: str | Path = "reports") -> tuple[Path, Path, BacktestAudit]:
        report = self.run()
        out_dir = Path(report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"hydra_prime_opportunity_audit_{self.start_raw}_to_{self.end_raw}".replace(":", "-")
        json_path = out_dir / f"{stem}.json"
        md_path = out_dir / f"{stem}.md"
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(report), handle, indent=2)
        with md_path.open("w", encoding="utf-8") as handle:
            handle.write(render_audit_markdown(report))
        return json_path, md_path, report


def render_audit_markdown(report: BacktestAudit) -> str:
    lines: List[str] = []
    lines.append("# HYDRA-PRIME Strict Real-Time-Only Opportunity Audit")
    lines.append("")
    lines.append(f"- Requested period: `{report.requested_start}` to `{report.requested_end}`")
    lines.append(f"- Data directory: `{report.data_dir}`")
    lines.append(f"- Strict real-time archive only: `{report.strict_realtime_only}`")
    lines.append(f"- Status: **{report.status}**")
    lines.append(f"- Generated at: `{report.generated_at}`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(report.note)
    lines.append("")
    if report.blockers:
        lines.append("## Blockers")
        lines.append("")
        for blocker in report.blockers:
            lines.append(f"- {blocker}")
        lines.append("")
    lines.append("## Required Feed Audit")
    lines.append("")
    lines.append("| Feed | Purpose | Status | Rows | First TS | Last TS | Reason |")
    lines.append("|---|---|---:|---:|---|---|---|")
    for feed in report.feed_audits:
        reason = feed.reason.replace("|", "/")
        lines.append(
            f"| `{feed.name}` | {feed.purpose} | **{feed.status}** | {feed.rows} | "
            f"{feed.first_timestamp or ''} | {feed.last_timestamp or ''} | {reason} |"
        )
    lines.append("")
    if report.opportunity_replay is not None:
        lines.append("## Opportunity replay")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(report.opportunity_replay, indent=2))
        lines.append("```")
        lines.append("")
    lines.append("## Output mode")
    lines.append("")
    lines.append("Opportunity detection only. No trade execution, no broker connection, no fill ledger, no ROI/P&L reporting.")
    lines.append("")
    return "\n".join(lines)
