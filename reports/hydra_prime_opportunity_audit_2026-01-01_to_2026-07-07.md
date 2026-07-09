# HYDRA-PRIME Strict Real-Time-Only Opportunity Audit

- Requested period: `2026-01-01` to `2026-07-07`
- Data directory: `data/realtime_archive`
- Strict real-time archive only: `True`
- Status: **BLOCKED**
- Generated at: `2026-07-09T15:36:44.337968+00:00`

## Verdict

No opportunity replay was produced because doing so would require missing data or simulated assumptions.

## Blockers

- cross_asset_price_ticks: Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Lead/lag detection cannot be reconstructed from daily data.
- vpin_trade_ticks: Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. VPIN requires real trade sequence, volume buckets, and side classification/inference.
- ohlcv_intraday_bars: Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Squeeze and day/month opportunity replay need intraday bars.
- options_flow_snapshots: Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Options flow cannot be truthfully replaced by underlying OHLC data.
- dark_pool_block_prints: Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Institutional block/dark-pool footprints are a separate data source.
- cot_positioning: Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. COT velocity cannot be inferred from price.
- physical_inventory_sensors: Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Cancelled warrants/inventory/production/demand are exogenous physical signals.

## Required Feed Audit

| Feed | Purpose | Status | Rows | First TS | Last TS | Reason |
|---|---|---:|---:|---|---|---|
| `cross_asset_price_ticks` | Cross-asset temporal leads | **MISSING_REPLACEMENT_OUTPUT** | 0 |  |  | Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Lead/lag detection cannot be reconstructed from daily data. |
| `vpin_trade_ticks` | VPIN/order-flow toxicity | **MISSING_REPLACEMENT_OUTPUT** | 0 |  |  | Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. VPIN requires real trade sequence, volume buckets, and side classification/inference. |
| `ohlcv_intraday_bars` | Volatility squeeze and opportunity context | **MISSING_REPLACEMENT_OUTPUT** | 0 |  |  | Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Squeeze and day/month opportunity replay need intraday bars. |
| `options_flow_snapshots` | Options-flow anomaly detector | **MISSING_REPLACEMENT_OUTPUT** | 0 |  |  | Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Options flow cannot be truthfully replaced by underlying OHLC data. |
| `dark_pool_block_prints` | Dark-pool/block footprint detector | **MISSING_REPLACEMENT_OUTPUT** | 0 |  |  | Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Institutional block/dark-pool footprints are a separate data source. |
| `cot_positioning` | Institutional COT velocity | **MISSING_REPLACEMENT_OUTPUT** | 0 |  |  | Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. COT velocity cannot be inferred from price. |
| `physical_inventory_sensors` | Physical supply/demand sensors | **MISSING_REPLACEMENT_OUTPUT** | 0 |  |  | Free/public replacement mode is enabled, but no normalized real-data CSV was produced for this feed. Run `acquire-replacements` on a network that can reach the replacement sources. Cancelled warrants/inventory/production/demand are exogenous physical signals. |

## Output mode

Opportunity detection only. No trade execution, no broker connection, no fill ledger, no ROI/P&L reporting.
