"""Free/public replacement feed registry and probe runner.

The registry is intentionally explicit about provenance. Some free feeds are
real-time exchange streams, while others are official delayed reports or proxies.
HYDRA-PRIME must surface those labels instead of pretending all feeds are equal.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import utcnow


@dataclass(frozen=True)
class FreeSource:
    feed: str
    name: str
    url: str
    provenance_label: str
    quality: str
    realtime: bool
    requires_key_env: Optional[str] = None
    method: str = "GET"
    payload: Optional[Dict[str, Any]] = None
    notes: str = ""


@dataclass
class ProbeResult:
    feed: str
    name: str
    status: str
    provenance_label: str
    realtime: bool
    quality: str
    url: str
    reason: str
    bytes_received: int = 0
    saved_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class FreeSourceProbeReport:
    generated_at: str
    status: str
    start: str
    end: str
    results: List[ProbeResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "status": self.status,
            "start": self.start,
            "end": self.end,
            "results": [asdict(r) for r in self.results],
        }


def _date_ms(value: str) -> int:
    d = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    return int(d.timestamp() * 1000)


def _date_yyyymmdd(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y%m%d")


def _date_year(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y")


def build_free_sources(start: str = "2026-01-01", end: str = "2026-01-31") -> List[FreeSource]:
    """Return concrete probe URLs for the researched free replacement stack."""

    start_ms = _date_ms(start)
    end_ms = _date_ms(end)
    start_day = _date_yyyymmdd(start)
    year = _date_year(start)
    return [
        # cross_asset_price_ticks
        FreeSource(
            "cross_asset_price_ticks",
            "Dukascopy XAUUSD quote ticks",
            f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{year}/00/01/00h_ticks.bi5",
            "HISTORICAL_QUOTE_TICK_ARCHIVE",
            "high_for_quote_ticks_medium_for_true_trades",
            False,
            notes="Hourly .bi5 quote tick archive; months are zero-indexed.",
        ),
        FreeSource(
            "cross_asset_price_ticks",
            "Binance BTCUSDT latest price",
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            "REAL_TIME_PUBLIC_EXCHANGE_REST",
            "high_for_crypto_leaders",
            True,
        ),
        FreeSource(
            "cross_asset_price_ticks",
            "Coinbase BTC-USD ticker",
            "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
            "REAL_TIME_PUBLIC_EXCHANGE_REST",
            "high_for_crypto_leaders",
            True,
        ),
        FreeSource(
            "cross_asset_price_ticks",
            "Kraken BTC/USD ticker",
            "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
            "REAL_TIME_PUBLIC_EXCHANGE_REST",
            "high_for_crypto_leaders",
            True,
        ),
        # vpin_trade_ticks
        FreeSource(
            "vpin_trade_ticks",
            "Binance BTCUSDT aggTrades archive probe",
            f"https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{start}.zip",
            "TRUE_VPIN_AVAILABLE_FOR_CRYPTO",
            "high_for_crypto_true_trades",
            False,
        ),
        FreeSource(
            "vpin_trade_ticks",
            "Coinbase BTC-USD trades",
            "https://api.exchange.coinbase.com/products/BTC-USD/trades?limit=100",
            "TRUE_VPIN_AVAILABLE_FOR_CRYPTO",
            "high_for_crypto_true_trades",
            True,
        ),
        FreeSource(
            "vpin_trade_ticks",
            "Kraken BTC/USD trades",
            "https://api.kraken.com/0/public/Trades?pair=XBTUSD",
            "TRUE_VPIN_AVAILABLE_FOR_CRYPTO",
            "high_for_crypto_true_trades",
            True,
        ),
        # ohlcv_intraday_bars
        FreeSource(
            "ohlcv_intraday_bars",
            "Binance BTCUSDT 1m kline archive probe",
            f"https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{start}.zip",
            "REAL_EXCHANGE_OHLCV_ARCHIVE",
            "high_for_crypto_ohlcv",
            False,
        ),
        FreeSource(
            "ohlcv_intraday_bars",
            "Coinbase BTC-USD candles",
            "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60",
            "REAL_TIME_PUBLIC_EXCHANGE_REST",
            "high_for_crypto_ohlcv_recent",
            True,
        ),
        FreeSource(
            "ohlcv_intraday_bars",
            "Kraken BTC/USD OHLC",
            "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1",
            "REAL_TIME_PUBLIC_EXCHANGE_REST",
            "high_for_crypto_ohlcv_recent",
            True,
        ),
        # options_flow_snapshots
        FreeSource(
            "options_flow_snapshots",
            "Deribit BTC historical option trades",
            "https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time?"
            + urllib.parse.urlencode(
                {
                    "currency": "BTC",
                    "kind": "option",
                    "start_timestamp": start_ms,
                    "end_timestamp": end_ms,
                    "count": 10,
                    "include_old": "true",
                }
            ),
            "REAL_EXCHANGE_OPTIONS_FLOW_CRYPTO",
            "high_for_btc_eth_options",
            False,
        ),
        FreeSource(
            "options_flow_snapshots",
            "CBOE equity put-call ratio CSV",
            "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv",
            "OFFICIAL_AGGREGATE_OPTIONS_SENTIMENT",
            "medium_aggregate_only",
            False,
        ),
        FreeSource(
            "options_flow_snapshots",
            "CBOE index put-call ratio CSV",
            "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv",
            "OFFICIAL_AGGREGATE_OPTIONS_SENTIMENT",
            "medium_aggregate_only",
            False,
        ),
        # dark_pool_block_prints
        FreeSource(
            "dark_pool_block_prints",
            "FINRA Reg SHO CNMS daily short volume",
            f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{start_day}.txt",
            "OFFICIAL_DAILY_SHORT_SALE_VOLUME",
            "medium_short_pressure_proxy",
            False,
        ),
        FreeSource(
            "dark_pool_block_prints",
            "FINRA OTC weekly summary GLD",
            "https://api.finra.org/data/group/otcMarket/name/weeklySummary",
            "OFFICIAL_DELAYED_ATS_OTC_BLOCK_DATA",
            "medium_delayed_ats_otc_summary",
            False,
            method="POST",
            payload={
                "compareFilters": [
                    {"compareType": "EQUAL", "fieldName": "issueSymbolIdentifier", "fieldValue": "GLD"}
                ],
                "limit": 5,
            },
        ),
        # cot_positioning
        FreeSource(
            "cot_positioning",
            "CFTC legacy COT compressed file",
            f"https://www.cftc.gov/files/dea/history/deacot{year}.zip",
            "OFFICIAL_WEEKLY_POSITIONING",
            "high_official_weekly",
            False,
        ),
        FreeSource(
            "cot_positioning",
            "CFTC disaggregated COT compressed file",
            f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip",
            "OFFICIAL_WEEKLY_POSITIONING",
            "high_official_weekly",
            False,
        ),
        # physical_inventory_sensors
        FreeSource(
            "physical_inventory_sensors",
            "LME warehouse and stock reports page",
            "https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports",
            "OFFICIAL_DELAYED_PHYSICAL_METAL_STOCKS",
            "medium_official_delayed",
            False,
        ),
        FreeSource(
            "physical_inventory_sensors",
            "CME COMEX delivery notices and stocks page",
            "https://www.cmegroup.com/solutions/clearing/operations-and-deliveries/nymex-delivery-notices.html",
            "OFFICIAL_OR_DERIVED_DAILY_COMEX_STOCKS",
            "medium_official_page_requires_parser",
            False,
        ),
        FreeSource(
            "physical_inventory_sensors",
            "EIA electricity retail sales metadata",
            "https://api.eia.gov/v2/electricity/retail-sales?api_key={EIA_API_KEY}",
            "OFFICIAL_ENERGY_DEMAND_PROXY",
            "medium_requires_free_key",
            False,
            requires_key_env="EIA_API_KEY",
        ),
        FreeSource(
            "physical_inventory_sensors",
            "FRED real yield DFII10",
            "https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&file_type=json&api_key={FRED_API_KEY}&limit=5&sort_order=desc",
            "OFFICIAL_MACRO_REAL_YIELD_PROXY",
            "high_requires_free_key",
            False,
            requires_key_env="FRED_API_KEY",
        ),
        FreeSource(
            "physical_inventory_sensors",
            "USGS Mineral Commodity Summaries 2025 page",
            "https://www.usgs.gov/publications/mineral-commodity-summaries-2025",
            "OFFICIAL_LOW_FREQUENCY_SUPPLY_CONTEXT",
            "medium_low_frequency",
            False,
        ),
    ]


def _request(source: FreeSource, timeout: float = 20.0) -> bytes:
    url = source.url
    if source.requires_key_env:
        key = os.environ.get(source.requires_key_env)
        if not key:
            raise RuntimeError(f"missing free API key env {source.requires_key_env}")
        url = url.replace("{" + source.requires_key_env + "}", urllib.parse.quote(key))
    data = None
    headers = {"User-Agent": "HydraPrime-FreeSourceProbe/0.1", "Accept": "*/*"}
    if source.payload is not None:
        data = json.dumps(source.payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json,text/csv,*/*"
    req = urllib.request.Request(url, data=data, headers=headers, method=source.method.upper())
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - public market-data URLs only
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
        return response.read()


def probe_free_sources(
    start: str,
    end: str,
    output_dir: str | Path = "data/free_source_probes",
    timeout: float = 20.0,
    max_bytes_to_save: int = 2_000_000,
) -> FreeSourceProbeReport:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: List[ProbeResult] = []
    for source in build_free_sources(start, end):
        safe_name = "_".join(
            c if c.isalnum() else "_" for c in f"{source.feed}_{source.name}".lower()
        ).strip("_")
        try:
            raw = _request(source, timeout=timeout)
            path = out_dir / f"{safe_name}.probe"
            path.write_bytes(raw[:max_bytes_to_save])
            results.append(
                ProbeResult(
                    feed=source.feed,
                    name=source.name,
                    status="OK",
                    provenance_label=source.provenance_label,
                    realtime=source.realtime,
                    quality=source.quality,
                    url=source.url,
                    reason=f"Downloaded {len(raw)} bytes from free/public source.",
                    bytes_received=len(raw),
                    saved_path=str(path),
                )
            )
        except Exception as exc:
            status = "NEEDS_FREE_API_KEY" if source.requires_key_env and "missing free API key" in str(exc) else "BLOCKED_OR_UNREACHABLE"
            results.append(
                ProbeResult(
                    feed=source.feed,
                    name=source.name,
                    status=status,
                    provenance_label=source.provenance_label,
                    realtime=source.realtime,
                    quality=source.quality,
                    url=source.url,
                    reason="Could not retrieve source without fabrication.",
                    error=str(exc),
                )
            )
    ok_feeds = {r.feed for r in results if r.status == "OK"}
    required_feeds = {s.feed for s in build_free_sources(start, end)}
    status = "OK" if required_feeds.issubset(ok_feeds) else "PARTIAL_OR_BLOCKED"
    return FreeSourceProbeReport(
        generated_at=utcnow().isoformat(),
        status=status,
        start=start,
        end=end,
        results=results,
    )


def render_probe_markdown(report: FreeSourceProbeReport) -> str:
    lines: List[str] = []
    lines.append("# HYDRA-PRIME Free Replacement Source Probe")
    lines.append("")
    lines.append(f"- Generated: `{report.generated_at}`")
    lines.append(f"- Range: `{report.start}` to `{report.end}`")
    lines.append(f"- Status: **{report.status}**")
    lines.append("")
    lines.append("| Feed | Source | Status | Provenance | Realtime | Bytes | Reason |")
    lines.append("|---|---|---:|---|---:|---:|---|")
    for result in report.results:
        reason = (result.reason + (f" Error: {result.error}" if result.error else "")).replace("|", "/")
        lines.append(
            f"| `{result.feed}` | {result.name} | **{result.status}** | `{result.provenance_label}` | "
            f"{str(result.realtime)} | {result.bytes_received} | {reason} |"
        )
    lines.append("")
    lines.append("## Truth rule")
    lines.append("")
    lines.append("A failed probe means the source was not available from the current runtime; it is not replaced with demo/synthetic data.")
    lines.append("")
    return "\n".join(lines)


def write_probe_report(report: FreeSourceProbeReport, report_dir: str | Path = "reports") -> tuple[Path, Path]:
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"free_source_probe_{report.start}_to_{report.end}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_probe_markdown(report), encoding="utf-8")
    return json_path, md_path
