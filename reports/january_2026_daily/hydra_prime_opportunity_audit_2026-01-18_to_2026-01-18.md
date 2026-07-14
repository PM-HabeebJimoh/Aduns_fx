# HYDRA-PRIME Strict Real-Time-Only Opportunity Audit

- Requested period: `2026-01-18` to `2026-01-18`
- Data directory: `data/realtime_archive`
- Strict real-time archive only: `True`
- Status: **BLOCKED**
- Generated at: `2026-07-09T12:53:44.828135+00:00`

## Verdict

No opportunity replay was produced because doing so would require missing data or simulated assumptions.

## Blockers

- cross_asset_price_ticks: Required feed is absent from manifest. Lead/lag detection cannot be reconstructed from daily data.
- vpin_trade_ticks: Required feed is absent from manifest. VPIN requires real trade sequence, volume buckets, and side classification/inference.
- ohlcv_intraday_bars: Required feed is absent from manifest. Squeeze and day/month opportunity replay need intraday bars.
- options_flow_snapshots: Required feed is absent from manifest. Options flow cannot be truthfully replaced by underlying OHLC data.
- dark_pool_block_prints: Required feed is absent from manifest. Institutional block/dark-pool footprints are a separate data source.
- cot_positioning: Required feed is absent from manifest. COT velocity cannot be inferred from price.
- physical_inventory_sensors: Required feed is absent from manifest. Cancelled warrants/inventory/production/demand are exogenous physical signals.

## Required Feed Audit

| Feed | Purpose | Status | Rows | First TS | Last TS | Reason |
|---|---|---:|---:|---|---|---|
| `cross_asset_price_ticks` | Cross-asset temporal leads | **MISSING** | 0 |  |  | Required feed is absent from manifest. Lead/lag detection cannot be reconstructed from daily data. |
| `vpin_trade_ticks` | VPIN/order-flow toxicity | **MISSING** | 0 |  |  | Required feed is absent from manifest. VPIN requires real trade sequence, volume buckets, and side classification/inference. |
| `ohlcv_intraday_bars` | Volatility squeeze and opportunity context | **MISSING** | 0 |  |  | Required feed is absent from manifest. Squeeze and day/month opportunity replay need intraday bars. |
| `options_flow_snapshots` | Options-flow anomaly detector | **MISSING** | 0 |  |  | Required feed is absent from manifest. Options flow cannot be truthfully replaced by underlying OHLC data. |
| `dark_pool_block_prints` | Dark-pool/block footprint detector | **MISSING** | 0 |  |  | Required feed is absent from manifest. Institutional block/dark-pool footprints are a separate data source. |
| `cot_positioning` | Institutional COT velocity | **MISSING** | 0 |  |  | Required feed is absent from manifest. COT velocity cannot be inferred from price. |
| `physical_inventory_sensors` | Physical supply/demand sensors | **MISSING** | 0 |  |  | Required feed is absent from manifest. Cancelled warrants/inventory/production/demand are exogenous physical signals. |

## Output mode

Opportunity detection only. No trade execution, no broker connection, no fill ledger, no ROI/P&L reporting.
