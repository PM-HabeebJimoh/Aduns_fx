from __future__ import annotations

import unittest

from aduns_fx.free_sources import build_free_sources, render_probe_markdown, FreeSourceProbeReport, ProbeResult


class TestFreeSourceRegistry(unittest.TestCase):
    def test_registry_covers_all_required_feed_families(self) -> None:
        sources = build_free_sources("2026-01-01", "2026-01-31")
        feeds = {source.feed for source in sources}
        self.assertEqual(
            feeds,
            {
                "cross_asset_price_ticks",
                "vpin_trade_ticks",
                "ohlcv_intraday_bars",
                "options_flow_snapshots",
                "dark_pool_block_prints",
                "cot_positioning",
                "physical_inventory_sensors",
            },
        )

    def test_sources_have_provenance_labels(self) -> None:
        for source in build_free_sources("2026-01-01", "2026-01-31"):
            self.assertTrue(source.provenance_label)
            self.assertTrue(source.quality)
            self.assertTrue(source.url.startswith("https://") or source.url.startswith("wss://"))

    def test_probe_markdown_renders_blocked_without_fabrication(self) -> None:
        report = FreeSourceProbeReport(
            generated_at="2026-07-09T00:00:00Z",
            status="PARTIAL_OR_BLOCKED",
            start="2026-01-01",
            end="2026-01-31",
            results=[
                ProbeResult(
                    feed="cross_asset_price_ticks",
                    name="Example",
                    status="BLOCKED_OR_UNREACHABLE",
                    provenance_label="REAL_TIME_PUBLIC_EXCHANGE_REST",
                    realtime=True,
                    quality="high",
                    url="https://example.com",
                    reason="Could not retrieve source without fabrication.",
                    error="network blocked",
                )
            ],
        )
        md = render_probe_markdown(report)
        self.assertIn("BLOCKED_OR_UNREACHABLE", md)
        self.assertIn("not replaced with demo/synthetic data", md)


if __name__ == "__main__":
    unittest.main()
