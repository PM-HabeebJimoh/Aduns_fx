from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone

from aduns_fx.engine import HydraPrimeEngine
from aduns_fx.models import (
    CotSnapshot,
    DarkPoolSnapshot,
    OHLCVBar,
    OptionSnapshot,
    PhysicalSnapshot,
    PriceTick,
    SignalResult,
    TradeTick,
)
from aduns_fx.signals import (
    CrossAssetLeadDetector,
    DarkPoolBlockTradeDetector,
    InstitutionalFootprintTracker,
    OptionsFlowAnomalyDetector,
    PhysicalWorldSensor,
    VPINCalculator,
    VolatilitySqueezeDetector,
    CorrelationDivergenceDetector,
)


def ts(i: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)


def day(i: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)


class TestEightSignals(unittest.TestCase):
    def test_cross_asset_temporal_lead_detects_pre_move(self) -> None:
        detector = CrossAssetLeadDetector()
        for i in range(60):
            btc = 100_000 + math.sin(i / 3) * 10
            paxg = 2_000 + math.sin(i / 4) * 0.2
            if i > 54:
                btc += (i - 54) * 1200
                paxg += (i - 54) * 9
            detector.update_price("BTC", btc, ts(i))
            detector.update_price("PAXG", paxg, ts(i))
            detector.update_price("XAUUSD", 2000.0, ts(i))
        signals = detector.evaluate(["XAUUSD"])
        xau = [s for s in signals if s.instrument == "XAUUSD"][0]
        self.assertTrue(xau.active)
        self.assertEqual(xau.direction, 1)
        self.assertGreaterEqual(xau.details["n_leading_signals"], 2)

    def test_options_flow_anomaly_detector(self) -> None:
        detector = OptionsFlowAnomalyDetector()
        for i in range(8):
            detector.update_snapshot(OptionSnapshot("XAUUSD", 1000, 1000, 100, 100, 18, 18, timestamp=day(i)))
        detector.update_snapshot(OptionSnapshot("XAUUSD", 5000, 900, 1400, 100, 28, 19, timestamp=day(9)))
        signal = detector.evaluate(["XAUUSD"])[0]
        self.assertTrue(signal.active)
        self.assertEqual(signal.direction, 1)
        self.assertIn("components", signal.details)

    def test_dark_pool_block_trade_detector(self) -> None:
        detector = DarkPoolBlockTradeDetector()
        for i in range(8):
            close = 100 + i
            detector.update_snapshot(DarkPoolSnapshot("XAUUSD", 400, 1000, 250, close=close, low=close - 1, block_buy_ratio=0.51, timestamp=day(i)))
        detector.update_snapshot(DarkPoolSnapshot("XAUUSD", 1500, 2000, 1000, close=109, low=108, block_buy_ratio=0.72, timestamp=day(9)))
        signal = detector.evaluate(["XAUUSD"])[0]
        self.assertTrue(signal.active)
        self.assertEqual(signal.direction, 1)
        names = [c[0] for c in signal.details["components"]]
        self.assertIn("short_squeeze_setup", names)

    def test_vpin_order_flow_toxicity_detector(self) -> None:
        detector = VPINCalculator()
        price = 100.0
        for i in range(1000):
            is_buy = i % 2 == 0
            price += 0.01 if is_buy else -0.01
            detector.add_trade("XAUUSD", price, 1.0, is_buy, ts(i))
        for i in range(260):
            price += 0.03
            detector.add_trade("XAUUSD", price, 1.0, True, ts(1000 + i))
        signal = detector.evaluate(["XAUUSD"])[0]
        self.assertTrue(signal.active, signal.details)
        self.assertEqual(signal.direction, 1)
        self.assertGreater(signal.details["vpin"], 0.55)

    def test_volatility_squeeze_detector(self) -> None:
        detector = VolatilitySqueezeDetector()
        for i in range(140):
            if i < 95:
                close = 100 + math.sin(i / 4) * 5
                span = 3.0
            else:
                close = 100 + math.sin(i) * 0.01
                span = 0.05
            detector.update_bar(OHLCVBar("XAUUSD", day(i), close, close + span, close - span, close, 1000))
        signal = detector.evaluate(["XAUUSD"])[0]
        self.assertTrue(signal.active, signal.details)
        self.assertEqual(signal.direction, 0)
        self.assertTrue(signal.details["bb_squeeze"] or signal.details["atr_compression"])

    def test_correlation_divergence_detector(self) -> None:
        detector = CorrelationDivergenceDetector()
        for i in range(80):
            ry = 1.5 + i * 0.002
            if i < 55:
                xau = 2050 - i * 0.8
            else:
                xau = 2000 + (i - 55) * 1.5
                ry = 1.6 + (i - 55) * 0.02
            detector.update_bar(OHLCVBar("REALYIELD", day(i), ry, ry, ry, ry, 0))
            detector.update_bar(OHLCVBar("XAUUSD", day(i), xau, xau, xau, xau, 0))
        signal = [s for s in detector.evaluate(["XAUUSD"]) if s.instrument == "XAUUSD"][0]
        self.assertTrue(signal.active, signal.details)
        self.assertLess(signal.direction, 0)

    def test_institutional_footprint_tracker(self) -> None:
        detector = InstitutionalFootprintTracker()
        for i, value in enumerate([0, 10, 25, 55, 110, 190]):
            detector.update_snapshot(CotSnapshot("XAUUSD", value, value * 0.8, 1000, day(i)))
        signal = detector.evaluate(["XAUUSD"])[0]
        self.assertTrue(signal.active, signal.details)
        self.assertEqual(signal.direction, 1)

    def test_physical_world_sensor(self) -> None:
        detector = PhysicalWorldSensor()
        for i in range(8):
            detector.update_snapshot(PhysicalSnapshot("XAUUSD", 1000, 80, 1000 - i * 3, 100, 101, 0, 0, 0, day(i)))
        detector.update_snapshot(PhysicalSnapshot("XAUUSD", 1000, 360, 850, 95, 112, 2.5, 1.8, 2.2, day(9)))
        signal = detector.evaluate(["XAUUSD"])[0]
        self.assertTrue(signal.active, signal.details)
        self.assertEqual(signal.direction, 1)
        self.assertGreater(signal.details["cancelled_warrant_ratio"], 0.30)


class TestFusionAndSystem(unittest.TestCase):
    def test_fusion_requires_three_independent_confirmations(self) -> None:
        engine = HydraPrimeEngine(instruments=["XAUUSD"])
        signals = [
            SignalResult("OPTIONS_FLOW", "XAUUSD", 1, 0.9, 0.9, True, "4-72 hours", 240),
            SignalResult("DARK_POOL_BLOCK", "XAUUSD", 1, 0.9, 0.9, True, "4-24 hours", 240),
        ]
        decision = engine.fusion.fuse("XAUUSD", signals, reference_price=2000)
        self.assertFalse(decision.fire)
        self.assertLess(decision.n_agreeing, 3)

        signals.append(SignalResult("VPIN_TOXICITY", "XAUUSD", 1, 0.95, 0.95, True, "15-120 minutes", 15))
        decision = engine.fusion.fuse("XAUUSD", signals, reference_price=2000)
        self.assertTrue(decision.fire, decision.warnings)
        self.assertEqual(decision.direction, 1)
        self.assertGreaterEqual(decision.pre_move_score, 70)
        self.assertGreater(decision.position.notional_size, 0)
        self.assertGreater(decision.position.leverage, 0)
        self.assertIn("Advisory only", decision.position.reason)

    def test_complete_synthetic_system_fires_xau_alert(self) -> None:
        from aduns_fx.testing_scenarios import build_bullish_xau_engine

        engine = build_bullish_xau_engine()
        decisions = engine.evaluate(["XAUUSD"])
        decision = decisions[0]
        self.assertTrue(decision.fire, (decision.pre_move_score, decision.warnings, engine.diagnostics()))
        self.assertEqual(decision.direction, 1)
        self.assertGreaterEqual(decision.n_agreeing, 3)
        self.assertGreaterEqual(decision.position.leverage, 2)
        self.assertGreater(decision.position.notional_size, 0)
        self.assertIn("Advisory only", decision.position.reason)
        diagnostics = engine.diagnostics()
        # Confirm that all eight signal families produced at least one reading.
        expected_types = {
            "CROSS_ASSET_LEAD",
            "OPTIONS_FLOW",
            "DARK_POOL_BLOCK",
            "VPIN_TOXICITY",
            "VOLATILITY_SQUEEZE",
            "CORRELATION_DIVERGENCE",
            "COT_VELOCITY",
            "PHYSICAL_WORLD",
        }
        self.assertTrue(expected_types.issubset(set(diagnostics["signals_by_type"])), diagnostics)


if __name__ == "__main__":
    unittest.main()
