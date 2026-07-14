from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aduns_fx.replacement_acquire import FreeReplacementAcquirer, render_replacement_report, ReplacementReport, ReplacementResult


class TestReplacementAcquirer(unittest.TestCase):
    def test_manifest_does_not_include_empty_missing_feeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            acq = FreeReplacementAcquirer(tmp, "2026-01-01", "2026-01-02", timeout=0.01)
            manifest = acq.write_manifest()
            self.assertTrue(manifest.exists())
            self.assertIn('"feeds": []', manifest.read_text(encoding="utf-8"))

    def test_replacement_report_states_no_synthetic_rows(self) -> None:
        report = ReplacementReport(
            requested_start="2026-01-01",
            requested_end="2026-01-31",
            data_dir="data/realtime_archive",
            generated_at="2026-07-09T00:00:00Z",
            status="PARTIAL_OR_BLOCKED",
            manifest_path="data/realtime_archive/manifest.json",
            results=[ReplacementResult("cross_asset_price_ticks", "Coinbase public candles", "BLOCKED", "network")],
            blockers=["cross_asset_price_ticks: replacement source did not produce a normalized real-data CSV"],
        )
        md = render_replacement_report(report)
        self.assertIn("Free Replacement Acquisition", md)
        self.assertIn("no demo or synthetic rows", md)


if __name__ == "__main__":
    unittest.main()
