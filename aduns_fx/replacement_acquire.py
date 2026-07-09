"""Acquire and normalize free replacement data sources for HYDRA-PRIME.

This is the operational counterpart to the research matrix. It attempts to turn
free/public replacement sources into HYDRA's required CSV feed files. It never
creates synthetic rows. If a source is unreachable, the corresponding feed is
left out of the manifest and the report states why.
"""

from __future__ import annotations

import csv
import io
import json
import math
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .data_sources import EiaClient, FredClient
from .models import utcnow


USER_AGENT = "HydraPrime-FreeReplacementAcquirer/0.1"


@dataclass
class ReplacementResult:
    feed_name: str
    source_name: str
    status: str
    reason: str
    rows_written: int = 0
    files_written: List[str] = field(default_factory=list)
    attempted_urls: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ReplacementReport:
    requested_start: str
    requested_end: str
    data_dir: str
    generated_at: str
    status: str
    manifest_path: str
    results: List[ReplacementResult]
    blockers: List[str]


def parse_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def to_iso_utc_from_seconds(seconds: int | float) -> str:
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def to_iso_utc_from_ms(ms: int | float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def to_iso_utc_from_us(us: int | float) -> str:
    return datetime.fromtimestamp(float(us) / 1_000_000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def http_bytes(url: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> bytes:
    data = None
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json,text/csv,*/*"
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - public market data URLs
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            return response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str], append: bool = False) -> int:
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = append and path.exists() and path.stat().st_size > 0
    with path.open("a" if append else "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


class FreeReplacementAcquirer:
    """Normalize free/public replacements into HYDRA CSV feeds."""

    def __init__(
        self,
        data_dir: str | Path,
        start: str,
        end: str,
        timeout: float = 30.0,
        fred_api_key: Optional[str] = None,
        eia_api_key: Optional[str] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.start_raw = start
        self.end_raw = end
        self.start = parse_date(start)
        self.end = parse_date(end)
        self.timeout = timeout
        self.fred_api_key = fred_api_key
        self.eia_api_key = eia_api_key
        self.results: List[ReplacementResult] = []
        self.manifest_feeds: List[Dict[str, Any]] = []

    def _add_manifest(self, name: str, path: Path, source: str, capture_mode: str, provenance: str) -> None:
        if not path.exists() or path.stat().st_size == 0:
            return
        self.manifest_feeds.append(
            {
                "name": name,
                "path": path.relative_to(self.data_dir).as_posix(),
                "source": source,
                "capture_mode": capture_mode,
                "provenance_label": provenance,
                "synthetic": False,
                "simulated": False,
            }
        )

    def acquire_coinbase_candles(self, products: Sequence[Tuple[str, str]] = (("BTC-USD", "BTC"),)) -> ReplacementResult:
        """Use Coinbase public candles as cross-asset price observations and OHLCV bars.

        This is a free replacement for leader ticks/ohlcv where true tick archives
        are unavailable. It uses real exchange OHLCV data; no interpolation is
        performed.
        """

        result = ReplacementResult("cross_asset_price_ticks", "Coinbase public candles", "PENDING", "")
        price_path = self.data_dir / "cross_asset_price_ticks.csv"
        ohlcv_path = self.data_dir / "ohlcv_intraday_bars.csv"
        price_fields = ["timestamp", "symbol", "price", "source", "provenance_label"]
        ohlcv_fields = ["timestamp", "symbol", "open", "high", "low", "close", "volume", "source", "provenance_label"]
        total_rows = 0
        failures = 0
        for product, symbol in products:
            for d in date_range(self.start, self.end):
                # Coinbase max is around 300 candles. Use 6-hour chunks for 1m bars.
                chunk_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                for chunk in range(4):
                    start_dt = chunk_start + timedelta(hours=chunk * 6)
                    end_dt = start_dt + timedelta(hours=5, minutes=59)
                    url = "https://api.exchange.coinbase.com/products/{}/candles?".format(product) + urllib.parse.urlencode(
                        {
                            "start": start_dt.isoformat().replace("+00:00", "Z"),
                            "end": end_dt.isoformat().replace("+00:00", "Z"),
                            "granularity": 60,
                        }
                    )
                    result.attempted_urls.append(url)
                    try:
                        data = json.loads(http_bytes(url, timeout=self.timeout).decode("utf-8"))
                        price_rows: List[Dict[str, Any]] = []
                        ohlcv_rows: List[Dict[str, Any]] = []
                        for item in data:
                            # Coinbase: [time, low, high, open, close, volume]
                            if not isinstance(item, list) or len(item) < 6:
                                continue
                            ts = to_iso_utc_from_seconds(item[0])
                            low, high, open_, close, volume = map(float, item[1:6])
                            price_rows.append(
                                {
                                    "timestamp": ts,
                                    "symbol": symbol,
                                    "price": close,
                                    "source": "Coinbase public candles",
                                    "provenance_label": "REAL_EXCHANGE_OHLCV_BAR_CLOSE_REPLACEMENT",
                                }
                            )
                            ohlcv_rows.append(
                                {
                                    "timestamp": ts,
                                    "symbol": symbol,
                                    "open": open_,
                                    "high": high,
                                    "low": low,
                                    "close": close,
                                    "volume": volume,
                                    "source": "Coinbase public candles",
                                    "provenance_label": "REAL_EXCHANGE_OHLCV_ARCHIVE",
                                }
                            )
                        if price_rows:
                            total_rows += write_csv(price_path, price_rows, price_fields, append=price_path.exists())
                            write_csv(ohlcv_path, ohlcv_rows, ohlcv_fields, append=ohlcv_path.exists())
                    except Exception as exc:
                        failures += 1
                        result.errors.append(f"{url}: {exc}")
                        if failures >= 3 and total_rows == 0:
                            result.status = "BLOCKED_OR_UNREACHABLE"
                            result.reason = "Coinbase candle replacement source unreachable."
                            self.results.append(result)
                            return result
        if total_rows:
            result.status = "OK"
            result.reason = "Normalized Coinbase candles to cross_asset_price_ticks and ohlcv_intraday_bars."
            result.rows_written = total_rows
            result.files_written = [str(price_path), str(ohlcv_path)]
            self._add_manifest("cross_asset_price_ticks", price_path, "Coinbase public candles", "free_public_replacement", "REAL_EXCHANGE_OHLCV_BAR_CLOSE_REPLACEMENT")
            self._add_manifest("ohlcv_intraday_bars", ohlcv_path, "Coinbase public candles", "free_public_replacement", "REAL_EXCHANGE_OHLCV_ARCHIVE")
        else:
            result.status = "MISSING"
            result.reason = "Coinbase returned no candle rows."
        self.results.append(result)
        return result

    def acquire_binance_aggtrades(self, symbols: Sequence[Tuple[str, str]] = (("BTCUSDT", "BTC"),)) -> ReplacementResult:
        result = ReplacementResult("vpin_trade_ticks", "Binance aggTrades public archive", "PENDING", "")
        out_path = self.data_dir / "vpin_trade_ticks.csv"
        fields = ["timestamp", "symbol", "price", "volume", "is_buy", "source", "provenance_label"]
        rows_total = 0
        failures = 0
        for binance_symbol, internal_symbol in symbols:
            for d in date_range(self.start, self.end):
                url = f"https://data.binance.vision/data/spot/daily/aggTrades/{binance_symbol}/{binance_symbol}-aggTrades-{d.isoformat()}.zip"
                result.attempted_urls.append(url)
                try:
                    raw = http_bytes(url, timeout=self.timeout)
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        name = archive.namelist()[0]
                        with archive.open(name) as handle:
                            text = io.TextIOWrapper(handle, encoding="utf-8")
                            reader = csv.reader(text)
                            rows: List[Dict[str, Any]] = []
                            for row in reader:
                                if len(row) < 7 or row[0].lower().startswith("agg"):
                                    continue
                                price = float(row[1])
                                qty = float(row[2])
                                timestamp = int(float(row[5]))
                                # Binance spot archive timestamps are microseconds from 2025 onward.
                                ts = to_iso_utc_from_us(timestamp) if timestamp > 10_000_000_000_000 else to_iso_utc_from_ms(timestamp)
                                buyer_maker = row[6].strip().lower() in {"true", "1"}
                                rows.append(
                                    {
                                        "timestamp": ts,
                                        "symbol": internal_symbol,
                                        "price": price,
                                        "volume": qty,
                                        "is_buy": str(not buyer_maker),
                                        "source": "Binance aggTrades public archive",
                                        "provenance_label": "TRUE_VPIN_AVAILABLE_FOR_CRYPTO",
                                    }
                                )
                            rows_total += write_csv(out_path, rows, fields, append=out_path.exists())
                except Exception as exc:
                    failures += 1
                    result.errors.append(f"{url}: {exc}")
                    if failures >= 3 and rows_total == 0:
                        result.status = "BLOCKED_OR_UNREACHABLE"
                        result.reason = "Binance aggTrades replacement source unreachable."
                        self.results.append(result)
                        return result
        if rows_total:
            result.status = "OK"
            result.reason = "Normalized Binance aggTrades to vpin_trade_ticks."
            result.rows_written = rows_total
            result.files_written = [str(out_path)]
            self._add_manifest("vpin_trade_ticks", out_path, "Binance aggTrades public archive", "free_public_replacement", "TRUE_VPIN_AVAILABLE_FOR_CRYPTO")
        else:
            result.status = "MISSING"
            result.reason = "Binance returned no aggTrade rows."
        self.results.append(result)
        return result

    def acquire_cboe_put_call(self) -> ReplacementResult:
        result = ReplacementResult("options_flow_snapshots", "CBOE put-call ratio CSV archives", "PENDING", "")
        out_path = self.data_dir / "options_flow_snapshots.csv"
        fields = ["timestamp", "instrument", "call_volume", "put_volume", "otm_call_volume", "otm_put_volume", "source", "provenance_label"]
        sources = [
            ("CBOE_EQUITY", "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv"),
            ("CBOE_INDEX", "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv"),
        ]
        rows_total = 0
        for instrument, url in sources:
            result.attempted_urls.append(url)
            try:
                text = http_bytes(url, timeout=self.timeout).decode("utf-8", errors="replace")
                reader = csv.reader(io.StringIO(text))
                rows: List[Dict[str, Any]] = []
                header_seen = False
                for row in reader:
                    if not row:
                        continue
                    if row[0].strip().upper() == "DATE":
                        header_seen = True
                        continue
                    if not header_seen or len(row) < 4:
                        continue
                    try:
                        dt = datetime.strptime(row[0].strip(), "%m/%d/%Y").date()
                    except ValueError:
                        continue
                    if dt < self.start or dt > self.end:
                        continue
                    rows.append(
                        {
                            "timestamp": datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                            "instrument": instrument,
                            "call_volume": int(float(row[1])),
                            "put_volume": int(float(row[2])),
                            "otm_call_volume": "",
                            "otm_put_volume": "",
                            "source": "CBOE put-call ratio CSV archives",
                            "provenance_label": "OFFICIAL_AGGREGATE_OPTIONS_SENTIMENT",
                        }
                    )
                rows_total += write_csv(out_path, rows, fields, append=out_path.exists())
            except Exception as exc:
                result.errors.append(f"{url}: {exc}")
        if rows_total:
            result.status = "OK"
            result.reason = "Normalized CBOE PCR CSVs to options_flow_snapshots."
            result.rows_written = rows_total
            result.files_written = [str(out_path)]
            self._add_manifest("options_flow_snapshots", out_path, "CBOE put-call ratio CSV archives", "official_delayed_archive", "OFFICIAL_AGGREGATE_OPTIONS_SENTIMENT")
        else:
            result.status = "BLOCKED_OR_UNREACHABLE"
            result.reason = "CBOE PCR replacement source unreachable or returned no in-range rows."
        self.results.append(result)
        return result

    def acquire_finra_regsho(self, symbols: Sequence[str] = ("GLD", "IAU", "SLV")) -> ReplacementResult:
        result = ReplacementResult("dark_pool_block_prints", "FINRA Reg SHO daily short-sale files", "PENDING", "")
        out_path = self.data_dir / "dark_pool_block_prints.csv"
        fields = ["timestamp", "instrument", "dark_pool_volume", "total_volume", "short_volume", "source", "provenance_label"]
        rows_total = 0
        failures = 0
        symbol_set = set(symbols)
        for d in date_range(self.start, self.end):
            url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d.strftime('%Y%m%d')}.txt"
            result.attempted_urls.append(url)
            try:
                text = http_bytes(url, timeout=self.timeout).decode("utf-8", errors="replace")
                reader = csv.DictReader(io.StringIO(text), delimiter="|")
                rows: List[Dict[str, Any]] = []
                for row in reader:
                    symbol = row.get("Symbol", "")
                    if symbol not in symbol_set:
                        continue
                    short_volume = int(float(row.get("ShortVolume", 0) or 0))
                    total_volume = int(float(row.get("TotalVolume", 0) or 0))
                    rows.append(
                        {
                            "timestamp": datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                            "instrument": symbol,
                            "dark_pool_volume": short_volume,
                            "total_volume": total_volume,
                            "short_volume": short_volume,
                            "source": "FINRA Reg SHO daily short-sale files",
                            "provenance_label": "OFFICIAL_DAILY_SHORT_SALE_VOLUME_PROXY",
                        }
                    )
                rows_total += write_csv(out_path, rows, fields, append=out_path.exists())
            except Exception as exc:
                failures += 1
                result.errors.append(f"{url}: {exc}")
                if failures >= 3 and rows_total == 0:
                    result.status = "BLOCKED_OR_UNREACHABLE"
                    result.reason = "FINRA Reg SHO replacement source unreachable."
                    self.results.append(result)
                    return result
        if rows_total:
            result.status = "OK"
            result.reason = "Normalized FINRA short-sale files to dark_pool_block_prints proxy."
            result.rows_written = rows_total
            result.files_written = [str(out_path)]
            self._add_manifest("dark_pool_block_prints", out_path, "FINRA Reg SHO daily short-sale files", "official_delayed_archive", "OFFICIAL_DAILY_SHORT_SALE_VOLUME_PROXY")
        else:
            result.status = "MISSING"
            result.reason = "FINRA returned no matching symbol rows."
        self.results.append(result)
        return result

    def acquire_cftc_cot(self) -> ReplacementResult:
        result = ReplacementResult("cot_positioning", "CFTC official COT compressed files", "PENDING", "")
        out_path = self.data_dir / "cot_positioning.csv"
        fields = ["timestamp", "instrument", "commercial_net", "noncommercial_net", "open_interest", "source", "provenance_label"]
        rows_total = 0
        years = sorted({self.start.year - 1, self.start.year, self.end.year})
        market_map = {
            "GOLD": "XAUUSD",
            "SILVER": "XAGUSD",
            "COPPER": "HG",
            "AUSTRALIAN DOLLAR": "AUDUSD",
            "BRITISH POUND": "GBPUSD",
            "JAPANESE YEN": "USDJPY",
            "SWISS FRANC": "USDCHF",
            "EURO FX": "EURUSD",
        }
        for year in years:
            url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
            result.attempted_urls.append(url)
            try:
                raw = http_bytes(url, timeout=self.timeout)
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    for name in archive.namelist():
                        if not name.lower().endswith((".txt", ".csv")):
                            continue
                        text = archive.read(name).decode("utf-8", errors="replace")
                        reader = csv.DictReader(io.StringIO(text))
                        rows: List[Dict[str, Any]] = []
                        for row in reader:
                            market = (row.get("Market_and_Exchange_Names") or row.get("Market and Exchange Names") or "").upper()
                            instrument = next((inst for key, inst in market_map.items() if key in market), None)
                            if not instrument:
                                continue
                            date_raw = row.get("Report_Date_as_YYYY-MM-DD") or row.get("As_of_Date_In_Form_YYMMDD") or row.get("Report_Date_as_MM_DD_YYYY")
                            try:
                                if date_raw and "-" in date_raw:
                                    dt = datetime.fromisoformat(date_raw).date()
                                elif date_raw and len(date_raw.strip()) == 6:
                                    dt = datetime.strptime(date_raw.strip(), "%y%m%d").date()
                                else:
                                    continue
                            except ValueError:
                                continue
                            # Include one year of warm-up, audit coverage will verify range.
                            commercial_long = float(row.get("Commercial_Positions_Long_All", 0) or 0)
                            commercial_short = float(row.get("Commercial_Positions_Short_All", 0) or 0)
                            noncom_long = float(row.get("Noncommercial_Positions_Long_All", 0) or 0)
                            noncom_short = float(row.get("Noncommercial_Positions_Short_All", 0) or 0)
                            oi = float(row.get("Open_Interest_All", 0) or 0)
                            rows.append(
                                {
                                    "timestamp": datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                                    "instrument": instrument,
                                    "commercial_net": commercial_long - commercial_short,
                                    "noncommercial_net": noncom_long - noncom_short,
                                    "open_interest": oi,
                                    "source": "CFTC official COT compressed files",
                                    "provenance_label": "OFFICIAL_WEEKLY_POSITIONING",
                                }
                            )
                        rows_total += write_csv(out_path, rows, fields, append=out_path.exists())
            except Exception as exc:
                result.errors.append(f"{url}: {exc}")
        if rows_total:
            result.status = "OK"
            result.reason = "Normalized CFTC COT archives to cot_positioning."
            result.rows_written = rows_total
            result.files_written = [str(out_path)]
            self._add_manifest("cot_positioning", out_path, "CFTC official COT compressed files", "official_delayed_archive", "OFFICIAL_WEEKLY_POSITIONING")
        else:
            result.status = "BLOCKED_OR_UNREACHABLE"
            result.reason = "CFTC COT replacement source unreachable or no mapped rows found."
        self.results.append(result)
        return result

    def acquire_physical_eia_fred(self) -> ReplacementResult:
        result = ReplacementResult("physical_inventory_sensors", "EIA/FRED official physical-macro proxies", "PENDING", "")
        out_path = self.data_dir / "physical_inventory_sensors.csv"
        fields = ["timestamp", "instrument", "electricity_demand_index", "metadata", "source", "provenance_label"]
        rows: List[Dict[str, Any]] = []
        # EIA industrial electricity demand proxy.
        if self.eia_api_key:
            try:
                eia_rows = EiaClient(api_key=self.eia_api_key).industrial_electricity_sales(limit=36)
                values = [v for _, v in eia_rows]
                if values:
                    mean_value = sum(values) / len(values)
                    variance = sum((v - mean_value) ** 2 for v in values) / max(1, len(values))
                    for ts, value in eia_rows:
                        z = 0.0 if variance <= 1e-12 else (value - mean_value) / math.sqrt(variance)
                        for instrument in ("HG", "XAGUSD", "XAUUSD"):
                            rows.append(
                                {
                                    "timestamp": ts.isoformat().replace("+00:00", "Z"),
                                    "instrument": instrument,
                                    "electricity_demand_index": z,
                                    "metadata": json.dumps({"latest_sales": value}),
                                    "source": "EIA industrial electricity sales",
                                    "provenance_label": "OFFICIAL_ENERGY_DEMAND_PROXY",
                                }
                            )
            except Exception as exc:
                result.errors.append(f"EIA: {exc}")
        else:
            result.errors.append("EIA: EIA_API_KEY not set")
        # FRED real-yield observations as a physical/macro proxy for gold.
        if self.fred_api_key:
            try:
                fred_rows = FredClient(api_key=self.fred_api_key).series("DFII10", limit=260)
                for ts, value in fred_rows:
                    rows.append(
                        {
                            "timestamp": ts.isoformat().replace("+00:00", "Z"),
                            "instrument": "XAUUSD",
                            "electricity_demand_index": "",
                            "metadata": json.dumps({"DFII10_real_yield": value}),
                            "source": "FRED DFII10 real yield",
                            "provenance_label": "OFFICIAL_MACRO_REAL_YIELD_PROXY",
                        }
                    )
            except Exception as exc:
                result.errors.append(f"FRED: {exc}")
        else:
            result.errors.append("FRED: FRED_API_KEY not set")
        rows_written = write_csv(out_path, rows, fields, append=False)
        if rows_written:
            result.status = "OK"
            result.reason = "Normalized EIA/FRED proxies to physical_inventory_sensors."
            result.rows_written = rows_written
            result.files_written = [str(out_path)]
            self._add_manifest("physical_inventory_sensors", out_path, "EIA/FRED official physical-macro proxies", "free_public_replacement", "OFFICIAL_PHYSICAL_MACRO_PROXY")
        else:
            result.status = "BLOCKED_OR_UNREACHABLE"
            result.reason = "EIA/FRED replacement sources unavailable or keys missing."
        self.results.append(result)
        return result

    def write_manifest(self) -> Path:
        manifest = {
            "created_at": utcnow().isoformat(),
            "purpose": "HYDRA-PRIME free replacement real-data manifest",
            "replacement_policy": "Use free/public replacement sources when original feed families are unavailable. Never fabricate data.",
            "feeds": self.manifest_feeds,
        }
        path = self.data_dir / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path

    def run(self) -> ReplacementReport:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Remove stale normalized replacement files so row counts reflect this run.
        for name in (
            "cross_asset_price_ticks.csv",
            "ohlcv_intraday_bars.csv",
            "vpin_trade_ticks.csv",
            "options_flow_snapshots.csv",
            "dark_pool_block_prints.csv",
            "cot_positioning.csv",
            "physical_inventory_sensors.csv",
        ):
            path = self.data_dir / name
            if path.exists():
                path.unlink()
        self.acquire_coinbase_candles()
        self.acquire_binance_aggtrades()
        self.acquire_cboe_put_call()
        self.acquire_finra_regsho()
        self.acquire_cftc_cot()
        self.acquire_physical_eia_fred()
        manifest_path = self.write_manifest()
        required = {
            "cross_asset_price_ticks",
            "vpin_trade_ticks",
            "ohlcv_intraday_bars",
            "options_flow_snapshots",
            "dark_pool_block_prints",
            "cot_positioning",
            "physical_inventory_sensors",
        }
        acquired = {entry["name"] for entry in self.manifest_feeds}
        blockers = [f"{name}: replacement source did not produce a normalized real-data CSV" for name in sorted(required - acquired)]
        for result in self.results:
            if result.status != "OK":
                blockers.append(f"{result.feed_name}/{result.source_name}: {result.status} — {result.reason}")
        status = "OK" if not blockers else "PARTIAL_OR_BLOCKED"
        return ReplacementReport(
            requested_start=self.start_raw,
            requested_end=self.end_raw,
            data_dir=str(self.data_dir),
            generated_at=utcnow().isoformat(),
            status=status,
            manifest_path=str(manifest_path),
            results=self.results,
            blockers=blockers,
        )

    def write_report(self, report: ReplacementReport, report_dir: str | Path = "reports") -> tuple[Path, Path]:
        out_dir = Path(report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"hydra_prime_replacement_acquisition_{self.start_raw}_to_{self.end_raw}"
        json_path = out_dir / f"{stem}.json"
        md_path = out_dir / f"{stem}.md"
        json_path.write_text(json.dumps(asdict(report), indent=2, default=str), encoding="utf-8")
        md_path.write_text(render_replacement_report(report), encoding="utf-8")
        return json_path, md_path


def render_replacement_report(report: ReplacementReport) -> str:
    lines = [
        "# HYDRA-PRIME Free Replacement Acquisition Report",
        "",
        f"- Requested range: `{report.requested_start}` to `{report.requested_end}`",
        f"- Data directory: `{report.data_dir}`",
        f"- Manifest: `{report.manifest_path}`",
        f"- Status: **{report.status}**",
        f"- Generated: `{report.generated_at}`",
        "",
        "## Blockers",
        "",
    ]
    if report.blockers:
        lines.extend(f"- {b}" for b in report.blockers)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Source results",
            "",
            "| Feed | Replacement source | Status | Rows | Files | Reason |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for result in report.results:
        reason = (result.reason + ("; errors: " + "; ".join(result.errors[:3]) if result.errors else "")).replace("|", "/")
        lines.append(
            f"| `{result.feed_name}` | {result.source_name} | **{result.status}** | {result.rows_written} | {len(result.files_written)} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## Truth rule",
            "",
            "Only rows downloaded from free/public replacement sources are written. Missing feeds remain blocked; no demo or synthetic rows are generated.",
            "",
        ]
    )
    return "\n".join(lines)
