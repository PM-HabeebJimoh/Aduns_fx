from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aduns_fx.backtest import REQUIRED_FEEDS, StrictRealDataBacktester


class TestStrictRealDataBacktestAudit(unittest.TestCase):
    def test_missing_real_time_archive_blocks_backtest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "missing"
            runner = StrictRealDataBacktester(data_dir, "2026-01-01", "2026-07-07")
            report = runner.audit()
            self.assertEqual(report.status, "BLOCKED")
            self.assertTrue(any("Data directory does not exist" in b for b in report.blockers))
            self.assertIsNone(report.opportunity_replay)

    def test_rejects_demo_or_non_realtime_manifest_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "feeds": [
                            {
                                "name": "cross_asset_price_ticks",
                                "path": "demo_prices.csv",
                                "source": "demo generated fixture",
                                "capture_mode": "historical_api",
                                "synthetic": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (data_dir / "demo_prices.csv").write_text("timestamp,symbol,price\n2026-01-01T00:00:00Z,XAUUSD,2000\n", encoding="utf-8")
            report = StrictRealDataBacktester(data_dir, "2026-01-01", "2026-07-07").audit()
            self.assertEqual(report.status, "BLOCKED")
            self.assertTrue(any("non-real" in b or "Required feed" in b for b in report.blockers))

    def test_execution_fills_are_not_required_for_opportunity_alerts(self) -> None:
        required_names = {feed.name for feed in REQUIRED_FEEDS}
        self.assertNotIn("actual_execution_fills", required_names)


if __name__ == "__main__":
    unittest.main()
