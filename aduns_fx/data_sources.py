"""Optional free-data adapters for HYDRA-PRIME.

The engine is feed-agnostic: tests and production can ingest models directly.
This module provides small stdlib-only adapters for common public HTTP APIs.
Network access is intentionally not required for the unit test suite.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .models import OHLCVBar, OptionSnapshot, PriceTick


class DataSourceError(RuntimeError):
    pass


def _http_json(url: str, timeout: float = 15.0, headers: Optional[Dict[str, str]] = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "AdunsFX-HydraPrime/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - public market data URLs
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception as exc:  # pragma: no cover - network dependent
        raise DataSourceError(f"Failed to fetch {url}: {exc}") from exc


class YahooChartClient:
    """Fetch OHLCV bars from Yahoo Finance's public chart endpoint."""

    BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def bars(self, symbol: str, range_: str = "6mo", interval: str = "1d") -> List[OHLCVBar]:
        params = urllib.parse.urlencode({"range": range_, "interval": interval})
        url = self.BASE.format(symbol=urllib.parse.quote(symbol, safe="")) + "?" + params
        data = _http_json(url)
        try:
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover
            raise DataSourceError(f"Unexpected Yahoo response for {symbol}") from exc
        bars: List[OHLCVBar] = []
        for i, ts in enumerate(timestamps):
            try:
                o = quote["open"][i]
                h = quote["high"][i]
                l = quote["low"][i]
                c = quote["close"][i]
                v = quote.get("volume", [0] * len(timestamps))[i] or 0.0
                if None in (o, h, l, c):
                    continue
                bars.append(
                    OHLCVBar(
                        symbol=symbol,
                        timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                        open=float(o),
                        high=float(h),
                        low=float(l),
                        close=float(c),
                        volume=float(v),
                    )
                )
            except (TypeError, ValueError):
                continue
        return bars

    def latest_tick(self, symbol: str) -> PriceTick:
        bars = self.bars(symbol, range_="1d", interval="1m")
        if not bars:
            raise DataSourceError(f"No latest Yahoo bars for {symbol}")
        last = bars[-1]
        return PriceTick(symbol=symbol, price=last.close, timestamp=last.timestamp)


class BinanceRestClient:
    """Fetch public Binance prices/trades without API keys."""

    BASE = "https://api.binance.com"

    def price(self, symbol: str) -> PriceTick:
        url = f"{self.BASE}/api/v3/ticker/price?" + urllib.parse.urlencode({"symbol": symbol})
        data = _http_json(url)
        return PriceTick(symbol=symbol, price=float(data["price"]))

    def aggregate_trades(self, symbol: str, limit: int = 1000) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/api/v3/aggTrades?" + urllib.parse.urlencode({"symbol": symbol, "limit": limit})
        return list(_http_json(url))


class DeribitClient:
    """Fetch Deribit public options summaries.

    Deribit does not directly provide the CBOE-style fields used by the engine;
    `option_snapshot` derives a practical proxy from call/put open interest and
    bid IVs for the chosen currency.
    """

    BASE = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"

    def book_summary(self, currency: str = "BTC", kind: str = "option") -> List[Dict[str, Any]]:
        params = urllib.parse.urlencode({"currency": currency, "kind": kind})
        data = _http_json(self.BASE + "?" + params)
        return list(data.get("result", []))

    def option_snapshot(self, currency: str = "BTC", instrument: Optional[str] = None) -> OptionSnapshot:
        rows = self.book_summary(currency)
        call_volume = put_volume = otm_call_volume = otm_put_volume = 0.0
        call_ivs: List[float] = []
        put_ivs: List[float] = []
        for row in rows:
            name = str(row.get("instrument_name", ""))
            volume = float(row.get("volume", 0.0) or 0.0)
            oi = float(row.get("open_interest", 0.0) or 0.0)
            iv = row.get("bid_iv") or row.get("mark_iv")
            is_call = name.endswith("-C")
            is_put = name.endswith("-P")
            if is_call:
                call_volume += volume or oi
                otm_call_volume += oi
                if iv is not None:
                    call_ivs.append(float(iv))
            elif is_put:
                put_volume += volume or oi
                otm_put_volume += oi
                if iv is not None:
                    put_ivs.append(float(iv))
        avg_call_iv = sum(call_ivs) / len(call_ivs) if call_ivs else None
        avg_put_iv = sum(put_ivs) / len(put_ivs) if put_ivs else None
        return OptionSnapshot(
            instrument=instrument or currency,
            call_volume=call_volume,
            put_volume=put_volume,
            otm_call_volume=otm_call_volume,
            otm_put_volume=otm_put_volume,
            iv_call_25d=avg_call_iv,
            iv_put_25d=avg_put_iv,
        )


class FredClient:
    """Small FRED JSON adapter. API key is optional for low-volume public use."""

    BASE = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    def series(self, series_id: str, limit: int = 120) -> List[tuple[datetime, float]]:
        params = {"series_id": series_id, "file_type": "json", "sort_order": "desc", "limit": str(limit)}
        if self.api_key:
            params["api_key"] = self.api_key
        url = self.BASE + "?" + urllib.parse.urlencode(params)
        data = _http_json(url)
        out: List[tuple[datetime, float]] = []
        for obs in data.get("observations", []):
            value = obs.get("value")
            if value in (None, "."):
                continue
            out.append((datetime.fromisoformat(obs["date"]).replace(tzinfo=timezone.utc), float(value)))
        out.reverse()
        return out


YAHOO_SYMBOLS = {
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCHF": "CHF=X",
    "DXY": "DX-Y.NYB",
    "TNX": "^TNX",
    "SPX": "ES=F",
    "HG": "HG=F",
}
