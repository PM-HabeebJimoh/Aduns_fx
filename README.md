# Aduns FX — HYDRA-PRIME

HYDRA-PRIME is a pure-Python **market pre-movement opportunity-alert engine**. Its job is to detect when a high-conviction market opportunity may be forming before price fully reacts.

> Important: this is research / decision-support software. It does **not** guarantee win rate, ROI, drawdown, or zero-loss days. It does **not** execute trades, route orders, connect to brokers, simulate fills, or require execution ledgers. Alerts include **advisory** trade parameters only.

## Output mode

HYDRA-PRIME is now explicitly:

```text
OPPORTUNITY DETECTION ONLY
NO TRADE EXECUTION
NO BROKER API
NO ORDER ROUTING
NO SIMULATED FILLS
ADVISORY TRADE PARAMETERS INCLUDED
NO P&L / ROI CLAIMS
```

The system emits alerts like:

```text
PRE-MOVEMENT OPPORTUNITY DETECTED
Instrument: XAUUSD
Bias: LONG-BIAS / SHORT-BIAS
Score: 0-100
Expected movement window
Signals that fired
Advisory leverage / notional / risk % / stop loss / take profit / max loss
```

## What is implemented

The repository contains a dependency-free alert engine with all eight signal families from the specification:

1. **Cross-asset temporal lead detection** — BTC/PAXG/DXY/TNX/HG/SPX leader moves projected to follower instruments.
2. **Options-flow anomaly detector** — put/call extremes, OTM call/put surges, 25-delta risk reversal skew.
3. **Dark-pool / block-trade detector** — off-exchange volume ratio, block side, short-squeeze footprint.
4. **VPIN order-flow toxicity** — volume-synchronised informed-trading pressure from trade ticks.
5. **Entropy collapse + volatility squeeze** — Bollinger width, ATR compression, sign-entropy collapse.
6. **Correlation divergence detector** — physically linked market relationships breaking from expected correlation.
7. **Institutional footprint tracker** — COT commercial positioning velocity and acceleration.
8. **Physical-world sensor fusion** — cancelled warrants, inventory drawdowns, production/demand gaps, congestion, power demand, trends.

The master engine fuses those signals with an AND-gated rule:

- score threshold defaults to `70/100`
- at least `3` agreeing independent signal types required
- volatility squeeze acts as an amplifier, not a standalone direction
- alert fires only when independent signal convergence is strong enough
- advisory execution parameters are included in the alert
- broker execution/order routing remain disabled and outside the system

## Repository layout

```text
aduns_fx/
  models.py              # serialisable market-data, signal, decision dataclasses
  math_utils.py          # dependency-free statistics helpers
  signals.py             # all eight pre-movement signal detectors
  engine.py              # detector orchestration and opportunity fusion engine
  formatting.py          # console/Telegram-style opportunity alert rendering
  data_sources.py        # optional stdlib HTTP clients for public data APIs
  acquire.py             # lawful public data acquisition attempts
  backtest.py            # strict real-data opportunity-feed audit
  testing_scenarios.py   # deterministic all-signal synthetic health scenario
  cli.py                 # demo, acquire, backtest/audit, and self-test CLI
tests/
  test_signals.py        # unit + end-to-end tests
  test_backtest.py       # strict data provenance tests
```

## Quick start

No third-party Python packages are required.

```bash
python -m unittest discover -v
python -m aduns_fx.cli demo
python -m aduns_fx.cli demo --json
python -m aduns_fx.cli live --config config/live.example.json --once
python -m aduns_fx.cli acquire --start 2026-01-01 --end 2026-07-07 --data-dir data/realtime_archive
python -m aduns_fx.cli backtest --start 2026-01-01 --end 2026-07-07 --data-dir data/realtime_archive
```

The demo runs an offline deterministic XAUUSD scenario where all eight detector families are exercised and the fusion engine produces a pre-movement opportunity alert.

## Strict real-data opportunity audit

The `backtest` CLI is now an opportunity-feed audit. It is intentionally provenance-gated. It refuses to output fabricated alerts from missing data and it does not calculate ROI/P&L because execution has been removed.

For strict real-data opportunity replay — **real-time data only, no demo, no simulation, no assumptions** — the data directory must contain `manifest.json` plus CSV archives for:

- `cross_asset_price_ticks`
- `vpin_trade_ticks`
- `ohlcv_intraday_bars`
- `options_flow_snapshots`
- `dark_pool_block_prints`
- `cot_positioning`
- `physical_inventory_sensors`

Each manifest feed must use a real-time archive capture mode such as `realtime_archive`, `broker_realtime_archive`, `exchange_realtime_archive`, or `vendor_realtime_archive`. The runner rejects names/flags such as demo, fixture, synthetic, generated, simulated, mock, or theoretical.

If data is missing, the runner writes a BLOCKED audit report instead of inventing alerts.

## Programmatic usage

```python
from aduns_fx import HydraPrimeEngine
from aduns_fx.models import PriceTick, TradeTick, OptionSnapshot
from aduns_fx.formatting import format_pre_move_signal

engine = HydraPrimeEngine(instruments=["XAUUSD"], capital=10_000)

engine.ingest_price(PriceTick("BTC", 105000))
engine.ingest_trade(TradeTick("XAUUSD", 2000.5, 10, True))
engine.ingest_options(OptionSnapshot("XAUUSD", call_volume=5000, put_volume=1000))

for decision in engine.evaluate(["XAUUSD"]):
    if decision.fire:
        print(format_pre_move_signal(decision))
```

## Optional live data adapters

`aduns_fx.data_sources` includes small stdlib-only clients for public endpoints:

- Yahoo Finance chart endpoint for OHLCV bars
- Binance public REST for crypto prices/trades
- Deribit public options summaries
- FRED observations

They are intentionally isolated from tests because public endpoints can rate-limit or change schemas.
