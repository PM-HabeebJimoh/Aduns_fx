"""Lawful public-data acquisition layer for HYDRA-PRIME.

This module attempts to download the required real-data feeds from public or
vendor-public sources. It deliberately refuses to fabricate files and marks
private/restricted feeds as blocked when they cannot be lawfully obtained.
"""

from __future__ import annotations

import csv
import json
import lzma
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .backtest import REQUIRED_FEEDS
from .models import utcnow


USER_AGENT = "AdunsFX-HydraPrime-DataAcquirer/0.1 (+lawful-public-data-only)"


@dataclass(frozen=True)
class AcquisitionSource:
    feed_name: str
    source_name: str
    status_if_unavailable: str
    urls: Tuple[str, ...]
    method: str = "GET"
    payload: Optional[Dict[str, Any]] = None
    notes: str = ""
    lawful_public: bool = True
    requires_private_account: bool = False
    requires_paid_or_access_agreement: bool = False


@dataclass
class AcquisitionResult:
    feed_name: str
    source_name: str
    status: str
    reason: str
    attempted_urls: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)
    rows_written: int = 0
    started_at: str = field(default_factory=lambda: utcnow().isoformat())
    finished_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AcquisitionReport:
    requested_start: str
    requested_end: str
    data_dir: str
    generated_at: str
    status: str
    results: List[AcquisitionResult]
    manifest_path: str
    blockers: List[str]


class DownloadError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _request_bytes(url: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json,text/csv,*/*"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - public market data URLs
            if resp.status >= 400:
                raise DownloadError(f"HTTP {resp.status}")
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(f"URL error: {exc.reason}") from exc
    except Exception as exc:
        raise DownloadError(str(exc)) from exc


def dukascopy_url(symbol: str, day: date, hour: int) -> str:
    # Dukascopy months are zero-indexed.
    month = day.month - 1
    return f"https://datafeed.dukascopy.com/datafeed/{symbol}/{day.year}/{month:02d}/{day.day:02d}/{hour:02d}h_ticks.bi5"


def decode_dukascopy_bi5(symbol: str, raw: bytes, hour_start: datetime) -> List[Dict[str, Any]]:
    """Decode a Dukascopy .bi5 tick file to rows.

    Dukascopy stores rows as big-endian: time_ms, ask, bid, ask_vol, bid_vol.
    Prices are integer pips; JPY pairs use 1/1000, most others use 1/100000.
    Metals are typically 1/1000 in Dukascopy.
    """

    if not raw:
        return []
    try:
        data = lzma.decompress(raw)
    except lzma.LZMAError as exc:
        raise DownloadError(f"Dukascopy LZMA decode failed: {exc}") from exc
    row_size = 20
    if len(data) % row_size != 0:
        raise DownloadError(f"Unexpected Dukascopy decoded length: {len(data)}")
    price_scale = 1000.0 if symbol.endswith("JPY") or symbol.startswith("XAU") or symbol.startswith("XAG") else 100000.0
    rows: List[Dict[str, Any]] = []
    for offset in range(0, len(data), row_size):
        time_ms, ask_i, bid_i, ask_vol, bid_vol = struct.unpack(">IIIff", data[offset : offset + row_size])
        ts = hour_start + timedelta(milliseconds=time_ms)
        bid = bid_i / price_scale
        ask = ask_i / price_scale
        rows.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "symbol": symbol,
                "bid": f"{bid:.6f}",
                "ask": f"{ask:.6f}",
                "price": f"{(bid + ask) / 2.0:.6f}",
                "bid_volume": f"{bid_vol:.4f}",
                "ask_volume": f"{ask_vol:.4f}",
                "volume": f"{(bid_vol + ask_vol):.4f}",
                # Quote ticks do not have true trade aggressor side. Keep blank
                # rather than inventing an is_buy value.
                "is_buy": "",
            }
        )
    return rows


def write_rows_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str], append: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and append
    mode = "a" if append else "w"
    with path.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


class PublicDataAcquirer:
    """Attempt lawful public acquisition for all required HYDRA feeds."""

    def __init__(self, data_dir: str | Path, start: str, end: str, timeout: float = 30.0) -> None:
        self.data_dir = Path(data_dir)
        self.start_raw = start
        self.end_raw = end
        self.start = _parse_date(start)
        self.end = _parse_date(end)
        self.timeout = timeout
        self.results: List[AcquisitionResult] = []
        self.manifest_feeds: List[Dict[str, Any]] = []

    def _finish(self, result: AcquisitionResult) -> AcquisitionResult:
        result.finished_at = utcnow().isoformat()
        self.results.append(result)
        return result

    def _download_probe(self, source: AcquisitionSource) -> AcquisitionResult:
        result = AcquisitionResult(feed_name=source.feed_name, source_name=source.source_name, status="PENDING", reason="")
        if source.requires_private_account:
            result.status = "PRIVATE_REQUIRED"
            result.reason = "This feed is private account data and cannot be scraped from public sources. Export/upload from broker/exchange is required."
            return self._finish(result)
        if source.requires_paid_or_access_agreement:
            result.status = "ACCESS_AGREEMENT_REQUIRED"
            result.reason = "This feed requires a paid/professional/vendor/access agreement; the acquirer will not bypass access controls."
            return self._finish(result)
        for url in source.urls:
            result.attempted_urls.append(url)
            try:
                raw = _request_bytes(url, source.payload, timeout=self.timeout)
                probe_path = self.data_dir / "raw" / source.feed_name / (source.source_name.replace(" ", "_") + "_probe.bin")
                probe_path.parent.mkdir(parents=True, exist_ok=True)
                probe_path.write_bytes(raw[: min(len(raw), 2_000_000)])
                result.files_written.append(str(probe_path))
                result.status = "PROBE_OK"
                result.reason = f"Downloaded {len(raw)} bytes from public source probe. Full normalisation may still be source-specific."
                result.metadata["bytes_received"] = len(raw)
                return self._finish(result)
            except DownloadError as exc:
                result.metadata.setdefault("errors", []).append({"url": url, "error": str(exc)})
                continue
        result.status = source.status_if_unavailable
        result.reason = "All public source download attempts failed or were unreachable from this sandbox."
        return self._finish(result)

    def acquire_dukascopy_ticks(self, symbols: Sequence[str], max_files: Optional[int] = None) -> AcquisitionResult:
        """Download and decode Dukascopy tick archives for quote-tick feeds.

        This can supply cross-asset quote ticks and OHLCV source ticks for FX and
        metals. It cannot supply true trade aggressor side for VPIN.
        """

        result = AcquisitionResult(feed_name="cross_asset_price_ticks", source_name="Dukascopy tick archive", status="PENDING", reason="")
        out_path = self.data_dir / "cross_asset_price_ticks.csv"
        fields = ["timestamp", "symbol", "price", "bid", "ask", "bid_volume", "ask_volume", "volume", "is_buy"]
        files_seen = 0
        rows_total = 0
        consecutive_failures = 0
        for symbol in symbols:
            for d in _date_range(self.start, self.end):
                for hour in range(24):
                    if max_files is not None and files_seen >= max_files:
                        break
                    url = dukascopy_url(symbol, d, hour)
                    result.attempted_urls.append(url)
                    files_seen += 1
                    try:
                        raw = _request_bytes(url, timeout=self.timeout)
                        hour_start = datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)
                        rows = decode_dukascopy_bi5(symbol, raw, hour_start)
                        if rows:
                            rows_total += write_rows_csv(out_path, rows, fields, append=out_path.exists())
                        consecutive_failures = 0
                    except DownloadError as exc:
                        consecutive_failures += 1
                        result.metadata.setdefault("errors", []).append({"url": url, "error": str(exc)})
                        # If the host is unreachable, do not burn time on tens of
                        # thousands of doomed hourly files.
                        if consecutive_failures >= 3 and rows_total == 0:
                            result.status = "UNREACHABLE"
                            result.reason = "Dukascopy public tick archive was unreachable from this sandbox."
                            return self._finish(result)
                if max_files is not None and files_seen >= max_files:
                    break
            if max_files is not None and files_seen >= max_files:
                break
        if rows_total > 0:
            result.status = "OK_PARTIAL" if max_files is not None else "OK"
            result.reason = "Downloaded and decoded public Dukascopy tick archive rows."
            result.files_written.append(str(out_path))
            result.rows_written = rows_total
            self.manifest_feeds.append(
                {
                    "name": "cross_asset_price_ticks",
                    "path": out_path.relative_to(self.data_dir).as_posix(),
                    "source": "Dukascopy public tick archive",
                    "capture_mode": "vendor_realtime_archive",
                    "synthetic": False,
                    "simulated": False,
                }
            )
            # Same real quote-tick archive can feed OHLCV resampling, but true
            # trade VPIN still needs trade ticks/aggressor side.
            self.manifest_feeds.append(
                {
                    "name": "ohlcv_intraday_bars",
                    "path": out_path.relative_to(self.data_dir).as_posix(),
                    "source": "Dukascopy public tick archive (OHLCV resampling source)",
                    "capture_mode": "vendor_realtime_archive",
                    "synthetic": False,
                    "simulated": False,
                }
            )
        else:
            result.status = "MISSING"
            result.reason = "No Dukascopy rows were downloaded."
        return self._finish(result)

    def acquire_public_probes(self) -> None:
        sources = [
            AcquisitionSource(
                feed_name="vpin_trade_ticks",
                source_name="Binance public aggTrades archive",
                status_if_unavailable="UNREACHABLE",
                urls=(
                    "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-01-01.zip",
                    "https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-01.zip",
                ),
                notes="Can supply crypto trade ticks; does not supply XAUUSD/FX true trade ticks.",
            ),
            AcquisitionSource(
                feed_name="options_flow_snapshots",
                source_name="Deribit public options summary",
                status_if_unavailable="UNREACHABLE",
                urls=("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option",),
                notes="Current public snapshot/proxy only unless historical option trade crawling is added and succeeds.",
            ),
            AcquisitionSource(
                feed_name="options_flow_snapshots",
                source_name="CBOE daily market statistics",
                status_if_unavailable="UNREACHABLE",
                urls=("https://www.cboe.com/markets/us/options/market-statistics/daily/",),
                notes="Public page is daily/current statistics, not a complete historical options-flow archive.",
            ),
            AcquisitionSource(
                feed_name="dark_pool_block_prints",
                source_name="FINRA OTC transparency API weekly summary GLD probe",
                status_if_unavailable="UNREACHABLE",
                urls=("https://api.finra.org/data/group/otcMarket/name/weeklySummary",),
                method="POST",
                payload={
                    "compareFilters": [
                        {"compareType": "EQUAL", "fieldName": "issueSymbolIdentifier", "fieldValue": "GLD"}
                    ],
                    "limit": 5,
                },
                notes="Public API probe for ATS/OTC summaries; block/professional details may require access terms.",
            ),
            AcquisitionSource(
                feed_name="cot_positioning",
                source_name="CFTC 2026 COT historical ZIP",
                status_if_unavailable="UNREACHABLE",
                urls=("https://www.cftc.gov/files/dea/history/deacot2026.zip",),
            ),
            AcquisitionSource(
                feed_name="physical_inventory_sensors",
                source_name="LME reports landing page probe",
                status_if_unavailable="ACCESS_AGREEMENT_OR_MANUAL_EXPORT_REQUIRED",
                urls=("https://www.lme.com/en/Market-data/Reports-and-data/Warehouse-and-stocks-reports",),
                notes="Complete historical cancelled-warrant/warehouse data generally needs vendor/LME export path.",
            ),

        ]
        for source in sources:
            self._download_probe(source)

    def write_manifest(self) -> Path:
        # Only include successful, verified real feed entries. Do not include
        # failed probes or partial binary probes as usable feeds.
        manifest = {
            "created_at": utcnow().isoformat(),
            "purpose": "HYDRA-PRIME strict real-data archive manifest",
            "feeds": self.manifest_feeds,
            "notes": [
                "Only feeds successfully downloaded and normalised by the lawful acquirer are included.",
                "Failed probes are recorded in reports, not promoted to backtest feeds.",
            ],
        }
        path = self.data_dir / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path

    def run(self, dukascopy_symbols: Sequence[str], max_dukascopy_files: Optional[int] = None) -> AcquisitionReport:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.acquire_dukascopy_ticks(dukascopy_symbols, max_files=max_dukascopy_files)
        self.acquire_public_probes()
        manifest_path = self.write_manifest()

        required = {feed.name for feed in REQUIRED_FEEDS}
        acquired = {entry["name"] for entry in self.manifest_feeds}
        blockers = [f"{name}: not acquired as a verified strict feed" for name in sorted(required - acquired)]
        for result in self.results:
            if result.status not in {"OK", "OK_PARTIAL", "PROBE_OK"}:
                blockers.append(f"{result.feed_name}/{result.source_name}: {result.status} — {result.reason}")
        status = "OK" if not blockers else "BLOCKED"
        return AcquisitionReport(
            requested_start=self.start_raw,
            requested_end=self.end_raw,
            data_dir=str(self.data_dir),
            generated_at=utcnow().isoformat(),
            status=status,
            results=self.results,
            manifest_path=str(manifest_path),
            blockers=blockers,
        )

    def write_report(self, report_dir: str | Path, report: AcquisitionReport) -> tuple[Path, Path]:
        out_dir = Path(report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"hydra_prime_acquisition_{self.start_raw}_to_{self.end_raw}".replace(":", "-")
        json_path = out_dir / f"{stem}.json"
        md_path = out_dir / f"{stem}.md"
        json_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        md_path.write_text(render_acquisition_markdown(report), encoding="utf-8")
        return json_path, md_path


def render_acquisition_markdown(report: AcquisitionReport) -> str:
    lines: List[str] = []
    lines.append("# HYDRA-PRIME Required Data Acquisition Report")
    lines.append("")
    lines.append(f"- Requested period: `{report.requested_start}` to `{report.requested_end}`")
    lines.append(f"- Data directory: `{report.data_dir}`")
    lines.append(f"- Manifest: `{report.manifest_path}`")
    lines.append(f"- Status: **{report.status}**")
    lines.append(f"- Generated at: `{report.generated_at}`")
    lines.append("")
    if report.blockers:
        lines.append("## Blockers")
        lines.append("")
        for blocker in report.blockers:
            lines.append(f"- {blocker}")
        lines.append("")
    lines.append("## Source Attempts")
    lines.append("")
    lines.append("| Feed | Source | Status | Rows | Files | Reason |")
    lines.append("|---|---|---:|---:|---:|---|")
    for result in report.results:
        reason = result.reason.replace("|", "/")
        lines.append(
            f"| `{result.feed_name}` | {result.source_name} | **{result.status}** | "
            f"{result.rows_written} | {len(result.files_written)} | {reason} |"
        )
        if result.metadata.get("errors"):
            lines.append(f"<!-- {json.dumps(result.metadata.get('errors')[:5])} -->")
    lines.append("")
    lines.append("## Non-negotiable truth")
    lines.append("")
    lines.append(
        "The acquirer does not fabricate data, bypass access controls, or create simulated feeds. "
        "Execution has been removed: this system only needs market/opportunity data feeds and never requires broker fill ledgers."
    )
    lines.append("")
    return "\n".join(lines)
