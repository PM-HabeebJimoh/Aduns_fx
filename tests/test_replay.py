from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from aduns_fx.backtest import REQUIRED_FEEDS, StrictRealDataBacktester
from aduns_fx.replay import OpportunityReplayRunner


class TestOpportunityReplay(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_strict_backtester_runs_replay_when_all_replacement_feeds_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            start_ts = "2026-01-01T00:00:00Z"
            end_ts = "2026-01-02T23:59:59.999999Z"
            feed_defs = {
                "cross_asset_price_ticks": (["timestamp", "symbol", "price"], [{"timestamp": start_ts, "symbol": "BTC", "price": 100}, {"timestamp": end_ts, "symbol": "BTC", "price": 101}]),
                "vpin_trade_ticks": (["timestamp", "symbol", "price", "volume", "is_buy"], [{"timestamp": start_ts, "symbol": "BTC", "price": 100, "volume": 1, "is_buy": "true"}, {"timestamp": end_ts, "symbol": "BTC", "price": 101, "volume": 1, "is_buy": "false"}]),
                "ohlcv_intraday_bars": (["timestamp", "symbol", "open", "high", "low", "close", "volume"], [{"timestamp": start_ts, "symbol": "BTC", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 10}, {"timestamp": end_ts, "symbol": "BTC", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 10}]),
                "options_flow_snapshots": (["timestamp", "instrument", "call_volume", "put_volume"], [{"timestamp": start_ts, "instrument": "BTC", "call_volume": 10, "put_volume": 8}, {"timestamp": end_ts, "instrument": "BTC", "call_volume": 11, "put_volume": 7}]),
                "dark_pool_block_prints": (["timestamp", "instrument", "dark_pool_volume", "total_volume"], [{"timestamp": start_ts, "instrument": "BTC", "dark_pool_volume": 10, "total_volume": 100}, {"timestamp": end_ts, "instrument": "BTC", "dark_pool_volume": 11, "total_volume": 100}]),
                "cot_positioning": (["timestamp", "instrument", "commercial_net", "open_interest"], [{"timestamp": start_ts, "instrument": "BTC", "commercial_net": 1, "open_interest": 100}, {"timestamp": end_ts, "instrument": "BTC", "commercial_net": 2, "open_interest": 100}]),
                "physical_inventory_sensors": (["timestamp", "instrument"], [{"timestamp": start_ts, "instrument": "BTC"}, {"timestamp": end_ts, "instrument": "BTC"}]),
            }
            feeds = []
            for name, (fields, rows) in feed_defs.items():
                path = data_dir / f"{name}.csv"
                self._write_csv(path, fields, rows)
                feeds.append({"name": name, "path": path.name, "source": "unit verification replacement", "capture_mode": "free_public_replacement", "synthetic": False, "simulated": False})
            (data_dir / "manifest.json").write_text(json.dumps({"replacement_policy": "test", "feeds": feeds}), encoding="utf-8")
            report = StrictRealDataBacktester(data_dir, "2026-01-01", "2026-01-02").run()
            self.assertEqual(report.status, "OK", report.blockers)
            self.assertIsNotNone(report.opportunity_replay)
            self.assertGreaterEqual(report.opportunity_replay["events_loaded"], 14)
            self.assertEqual(report.opportunity_replay["evaluation_days"], 2)


if __name__ == "__main__":
    unittest.main()
