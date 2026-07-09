"""Live HYDRA-PRIME opportunity scanner.

This module runs the engine in live alert mode. It does not execute trades. It
polls configured public/live data adapters, evaluates the opportunity engine,
and emits alerts to stdout, JSONL, and optionally a webhook.
"""

from __future__ import annotations

import json
import os
import time
import traceback
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .data_sources import BinanceRestClient, DeribitClient, YahooChartClient, YAHOO_SYMBOLS
from .engine import HydraPrimeEngine
from .formatting import decision_to_json, format_pre_move_signal
from .models import Decision, OHLCVBar, PriceTick, TradeTick, utcnow


DEFAULT_LIVE_INSTRUMENTS = ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "HG"]
DEFAULT_LEADER_SYMBOLS = ["BTC", "PAXG", "DXY", "TNX", "SPX", "HG", "XAUUSD", "XAGUSD"]


@dataclass
class FeedStatus:
    source: str
    ok: bool
    message: str
    rows: int = 0
    symbols: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class LiveRunResult:
    status: str
    generated_at: str
    cycle: int
    alerts_count: int
    alerts: List[Dict[str, Any]]
    feed_statuses: List[FeedStatus]
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "cycle": self.cycle,
            "alerts_count": self.alerts_count,
            "alerts": self.alerts,
            "feed_statuses": [asdict(s) for s in self.feed_statuses],
            "diagnostics": self.diagnostics,
        }


@dataclass
class LiveConfig:
    instruments: List[str] = field(default_factory=lambda: list(DEFAULT_LIVE_INSTRUMENTS))
    capital: float = 10_000.0
    poll_interval_seconds: float = 60.0
    alert_log: str = "logs/hydra_prime_alerts.jsonl"
    health_report: str = "reports/hydra_prime_live_health.json"
    webhook_url_env: str = "HYDRA_ALERT_WEBHOOK_URL"
    enable_yahoo: bool = True
    enable_binance: bool = True
    enable_deribit: bool = True
    yahoo_range: str = "6mo"
    yahoo_interval: str = "1d"
    binance_trade_limit: int = 1000

    @classmethod
    def from_file(cls, path: str | Path) -> "LiveConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg = cls()
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg


class AlertSink:
    """Emit opportunity alerts without executing trades."""

    def __init__(self, alert_log: str | Path, webhook_url: Optional[str] = None) -> None:
        self.alert_log = Path(alert_log)
        self.webhook_url = webhook_url
        self.alert_log.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, decision: Decision) -> None:
        text = format_pre_move_signal(decision)
        print(text)
        print()
        record = {
            "timestamp": utcnow().isoformat(),
            "text": text,
            "decision": json.loads(decision_to_json(decision)),
        }
        with self.alert_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
        if self.webhook_url:
            self._post_webhook(record)

    def _post_webhook(self, record: Dict[str, Any]) -> None:
        data = json.dumps(record).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url or "",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "HydraPrimeLive/0.1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - user configured webhook
                resp.read()
        except Exception as exc:
            print(f"[WARN] webhook delivery failed: {exc}")


class LiveOpportunityScanner:
    """Poll live/public feeds and emit HYDRA opportunity alerts."""

    def __init__(self, config: LiveConfig) -> None:
        self.config = config
        self.engine = HydraPrimeEngine(instruments=config.instruments, capital=config.capital)
        self.yahoo = YahooChartClient()
        self.binance = BinanceRestClient()
        self.deribit = DeribitClient()
        self.sink = AlertSink(config.alert_log, webhook_url=os.environ.get(config.webhook_url_env, "") or None)
        self.cycle = 0
        self._alert_keys_seen: set[str] = set()

    @staticmethod
    def _copy_bar_symbol(bar: OHLCVBar, symbol: str) -> OHLCVBar:
        return OHLCVBar(
            symbol=symbol,
            timestamp=bar.timestamp,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )

    def _poll_yahoo(self) -> FeedStatus:
        if not self.config.enable_yahoo:
            return FeedStatus("yahoo", True, "disabled", 0, [])
        needed = set(self.config.instruments) | set(DEFAULT_LEADER_SYMBOLS) | {"REALYIELD"}
        rows = 0
        symbols_ok: List[str] = []
        errors: List[str] = []
        for internal_symbol, yahoo_symbol in YAHOO_SYMBOLS.items():
            if internal_symbol not in needed:
                continue
            try:
                bars = self.yahoo.bars(yahoo_symbol, range_=self.config.yahoo_range, interval=self.config.yahoo_interval)
                for bar in bars:
                    self.engine.ingest_bar(self._copy_bar_symbol(bar, internal_symbol))
                if bars:
                    self.engine.ingest_price(PriceTick(internal_symbol, bars[-1].close, bars[-1].timestamp))
                    rows += len(bars)
                    symbols_ok.append(internal_symbol)
            except Exception as exc:
                errors.append(f"{internal_symbol}/{yahoo_symbol}: {exc}")
        if rows:
            return FeedStatus("yahoo", True, f"loaded {rows} OHLCV rows", rows, symbols_ok)
        return FeedStatus("yahoo", False, "no Yahoo data loaded", 0, symbols_ok, "; ".join(errors[:5]) or None)

    def _poll_binance(self) -> FeedStatus:
        if not self.config.enable_binance:
            return FeedStatus("binance", True, "disabled", 0, [])
        rows = 0
        symbols_ok: List[str] = []
        errors: List[str] = []
        for binance_symbol, internal_symbol in (("BTCUSDT", "BTC"), ("PAXGUSDT", "PAXG")):
            try:
                tick = self.binance.price(binance_symbol)
                self.engine.ingest_price(PriceTick(internal_symbol, tick.price, tick.timestamp))
                symbols_ok.append(internal_symbol)
                rows += 1
            except Exception as exc:
                errors.append(f"price {binance_symbol}: {exc}")
            try:
                trades = self.binance.aggregate_trades(binance_symbol, limit=self.config.binance_trade_limit)
                for trade in trades:
                    # Binance aggTrades: m=True means buyer is maker, so taker
                    # aggressor was sell; is_buy is false. If field absent,
                    # let VPIN infer side from price.
                    is_buy = None
                    if "m" in trade:
                        is_buy = not bool(trade["m"])
                    ts = utcnow()
                    if "T" in trade:
                        ts = datetime.fromtimestamp(int(trade["T"]) / 1000, tz=utcnow().tzinfo)
                    self.engine.ingest_trade(
                        TradeTick(
                            symbol=internal_symbol,
                            price=float(trade.get("p") or trade.get("price")),
                            volume=float(trade.get("q") or trade.get("quantity") or 0.0),
                            is_buy=is_buy,
                            timestamp=ts,
                        )
                    )
                if trades:
                    rows += len(trades)
            except Exception as exc:
                errors.append(f"trades {binance_symbol}: {exc}")
        if rows:
            return FeedStatus("binance", True, f"loaded {rows} price/trade rows", rows, symbols_ok)
        return FeedStatus("binance", False, "no Binance data loaded", 0, symbols_ok, "; ".join(errors[:5]) or None)

    def _poll_deribit(self) -> FeedStatus:
        if not self.config.enable_deribit:
            return FeedStatus("deribit", True, "disabled", 0, [])
        rows = 0
        symbols_ok: List[str] = []
        errors: List[str] = []
        for currency in ("BTC", "ETH"):
            try:
                snapshot = self.deribit.option_snapshot(currency=currency, instrument=currency)
                self.engine.ingest_options(snapshot)
                rows += 1
                symbols_ok.append(currency)
            except Exception as exc:
                errors.append(f"{currency}: {exc}")
        if rows:
            return FeedStatus("deribit", True, f"loaded {rows} option snapshots", rows, symbols_ok)
        return FeedStatus("deribit", False, "no Deribit data loaded", 0, symbols_ok, "; ".join(errors[:5]) or None)

    def poll_feeds(self) -> List[FeedStatus]:
        statuses = [self._poll_yahoo(), self._poll_binance(), self._poll_deribit()]
        return statuses

    def scan_once(self) -> LiveRunResult:
        self.cycle += 1
        feed_statuses = self.poll_feeds()
        decisions = self.engine.evaluate(self.config.instruments)
        alerts = [d for d in decisions if d.fire]
        emitted: List[Decision] = []
        for decision in alerts:
            key = f"{decision.instrument}:{decision.direction}:{decision.pre_move_score}:{decision.lead_time_estimate}"
            if key in self._alert_keys_seen:
                continue
            self._alert_keys_seen.add(key)
            self.sink.emit(decision)
            emitted.append(decision)

        any_feed_ok = any(s.ok and s.rows > 0 for s in feed_statuses)
        status = "LIVE" if any_feed_ok else "NO_LIVE_FEEDS"
        result = LiveRunResult(
            status=status,
            generated_at=utcnow().isoformat(),
            cycle=self.cycle,
            alerts_count=len(alerts),
            alerts=[json.loads(decision_to_json(d)) for d in alerts],
            feed_statuses=feed_statuses,
            diagnostics=self.engine.diagnostics(),
        )
        self.write_health(result)
        return result

    def write_health(self, result: LiveRunResult) -> None:
        path = Path(self.config.health_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")

    def run_forever(self, cycles: Optional[int] = None) -> None:
        completed = 0
        while True:
            try:
                result = self.scan_once()
                print(f"[{result.generated_at}] status={result.status} alerts={result.alerts_count} cycle={result.cycle}")
                for status in result.feed_statuses:
                    print(f"  feed={status.source} ok={status.ok} rows={status.rows} message={status.message}")
                    if status.error:
                        print(f"    error={status.error}")
            except KeyboardInterrupt:
                raise
            except Exception:
                print("[ERROR] live scan cycle failed")
                print(traceback.format_exc())
            completed += 1
            if cycles is not None and completed >= cycles:
                break
            time.sleep(max(1.0, float(self.config.poll_interval_seconds)))
