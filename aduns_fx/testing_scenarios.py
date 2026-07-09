"""Synthetic scenarios used by tests and the CLI demo.

The scenario deliberately creates a bullish XAUUSD confluence across all eight
signal families. It is not a backtest; it is a deterministic system health
fixture proving that ingestion, detectors, and opportunity fusion work end to
end without requiring external APIs.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import List

from .engine import HydraPrimeEngine
from .models import (
    CotSnapshot,
    DarkPoolSnapshot,
    OHLCVBar,
    OptionSnapshot,
    PhysicalSnapshot,
    PriceTick,
    TradeTick,
)


def _ts(i: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)


def _daily(i: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)


def seed_cross_asset_leads(engine: HydraPrimeEngine) -> None:
    # Stable leader history, then abrupt BTC/PAXG bullish repricing while XAUUSD
    # itself remains almost unchanged: this is the cross-venue lead window.
    for i in range(70):
        btc = 100000.0 + math.sin(i / 3) * 20.0
        paxg = 2000.0 + math.sin(i / 4) * 0.30
        xau = 2000.0 + math.sin(i / 5) * 0.10
        if i >= 65:
            btc += (i - 64) * 900.0
            paxg += (i - 64) * 8.0
            # follower deliberately not repriced yet
            xau = 2000.0 + math.sin(i / 5) * 0.05
        engine.ingest_price(PriceTick("BTC", btc, _ts(i)))
        engine.ingest_price(PriceTick("PAXG", paxg, _ts(i)))
        engine.ingest_price(PriceTick("XAUUSD", xau, _ts(i)))


def seed_volatility_squeeze(engine: HydraPrimeEngine) -> None:
    # Wide/normal range first, then a tightly compressed range.
    for i in range(140):
        if i < 95:
            close = 2000.0 + math.sin(i / 4.0) * 15.0 + math.cos(i / 9.0) * 4.0
            span = 6.0
        else:
            close = 2000.0 + math.sin(i / 2.0) * 0.08
            span = 0.20
        bar = OHLCVBar(
            symbol="XAUUSD",
            timestamp=_daily(i),
            open=close - 0.05,
            high=close + span / 2,
            low=close - span / 2,
            close=close,
            volume=1000.0 + i,
        )
        engine.ingest_bar(bar)


def seed_correlation_divergence(engine: HydraPrimeEngine) -> None:
    # Gold and real yields should be negatively correlated. The final section
    # forces them to rise together, creating a reversion/divergence alert.
    for i in range(80):
        real_yield = 1.5 + i * 0.002
        if i < 55:
            xau = 2050.0 - i * 0.8 + math.sin(i / 3) * 1.5
        else:
            # Bullish divergence: real yields fall, but gold also falls. In an
            # inverse relationship, gold is the side expected to revert upward.
            xau = 2000.0 - (i - 55) * 1.2
            real_yield = 1.6 - (i - 55) * 0.018
        # Feed directly to the correlation detector so the squeeze fixture's
        # final compressed XAUUSD bars are not overwritten.
        engine.correlation.update_bar(OHLCVBar("REALYIELD", _daily(i), real_yield, real_yield, real_yield, real_yield, 0.0))
        engine.correlation.update_bar(OHLCVBar("XAUUSD", _daily(i), xau, xau + 1, xau - 1, xau, 1000.0))


def seed_options_flow(engine: HydraPrimeEngine) -> None:
    for i in range(12):
        engine.ingest_options(
            OptionSnapshot(
                instrument="XAUUSD",
                call_volume=1000.0,
                put_volume=950.0 + i * 5,
                otm_call_volume=120.0,
                otm_put_volume=110.0,
                iv_call_25d=18.0,
                iv_put_25d=18.5,
                underlying_price=2000.0,
                timestamp=_daily(i),
            )
        )
    engine.ingest_options(
        OptionSnapshot(
            instrument="XAUUSD",
            call_volume=5200.0,
            put_volume=1000.0,
            otm_call_volume=1400.0,
            otm_put_volume=120.0,
            iv_call_25d=27.0,
            iv_put_25d=19.0,
            underlying_price=2000.0,
            timestamp=_daily(13),
        )
    )


def seed_dark_pool(engine: HydraPrimeEngine) -> None:
    for i in range(8):
        close = 1988.0 + i * 1.0
        engine.ingest_dark_pool(
            DarkPoolSnapshot(
                instrument="XAUUSD",
                dark_pool_volume=400_000.0,
                total_volume=1_000_000.0,
                short_volume=280_000.0,
                close=close,
                low=close - 2.0 + i * 0.2,
                high=close + 2.0,
                block_buy_ratio=0.52,
                timestamp=_daily(i),
            )
        )
    engine.ingest_dark_pool(
        DarkPoolSnapshot(
            instrument="XAUUSD",
            dark_pool_volume=1_400_000.0,
            total_volume=2_000_000.0,
            short_volume=1_000_000.0,
            close=1998.0,
            low=1995.0,
            high=2001.0,
            block_buy_ratio=0.72,
            timestamp=_daily(9),
        )
    )


def seed_vpin(engine: HydraPrimeEngine) -> None:
    # Balanced historical flow establishes a low-to-normal VPIN baseline.
    price = 2000.0
    for i in range(1000):
        is_buy = i % 2 == 0
        price += 0.01 if is_buy else -0.01
        engine.ingest_trade(TradeTick("XAUUSD", price, 1.0, is_buy, _ts(i)))
    # Informed buy wave: sustained same-side pressure.
    for i in range(260):
        price += 0.03
        engine.ingest_trade(TradeTick("XAUUSD", price, 1.0, True, _ts(1000 + i)))


def seed_cot(engine: HydraPrimeEngine) -> None:
    # Accelerating commercial net long build.
    values = [0, 10, 25, 55, 105, 180]
    noncom = [0, 8, 20, 48, 95, 160]
    for i, (c, n) in enumerate(zip(values, noncom)):
        engine.ingest_cot(
            CotSnapshot(
                instrument="XAUUSD",
                commercial_net=float(c),
                noncommercial_net=float(n),
                open_interest=1000.0,
                timestamp=_daily(i * 7),
            )
        )


def seed_physical_world(engine: HydraPrimeEngine) -> None:
    for i in range(8):
        engine.ingest_physical(
            PhysicalSnapshot(
                instrument="XAUUSD",
                total_warrants=1000.0,
                cancelled_warrants=80.0,
                inventory=1000.0 - i * 5.0,
                production=100.0,
                demand=101.0,
                port_congestion_index=0.2,
                electricity_demand_index=0.1,
                google_trends_index=0.0,
                timestamp=_daily(i),
            )
        )
    engine.ingest_physical(
        PhysicalSnapshot(
            instrument="XAUUSD",
            total_warrants=1000.0,
            cancelled_warrants=360.0,
            inventory=850.0,
            production=95.0,
            demand=112.0,
            port_congestion_index=2.8,
            electricity_demand_index=1.8,
            google_trends_index=2.4,
            timestamp=_daily(9),
        )
    )


def build_bullish_xau_engine(capital: float = 10_000.0) -> HydraPrimeEngine:
    engine = HydraPrimeEngine(instruments=["XAUUSD"], capital=capital)
    seed_cross_asset_leads(engine)
    seed_volatility_squeeze(engine)
    seed_correlation_divergence(engine)
    seed_options_flow(engine)
    seed_dark_pool(engine)
    seed_vpin(engine)
    seed_cot(engine)
    seed_physical_world(engine)
    return engine


def run_bullish_xau_demo() -> List[str]:
    from .formatting import format_pre_move_signal

    engine = build_bullish_xau_engine()
    return [format_pre_move_signal(d, capital=engine.risk_manager.capital) for d in engine.evaluate(["XAUUSD"])]
