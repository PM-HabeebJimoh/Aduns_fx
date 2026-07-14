# HYDRA-PRIME Free Replacement Acquisition Report

- Requested range: `2026-01-01` to `2026-07-07`
- Data directory: `data/realtime_archive`
- Manifest: `data/realtime_archive/manifest.json`
- Status: **PARTIAL_OR_BLOCKED**
- Generated: `2026-07-09T15:36:44.241189+00:00`

## Blockers

- cot_positioning: replacement source did not produce a normalized real-data CSV
- cross_asset_price_ticks: replacement source did not produce a normalized real-data CSV
- dark_pool_block_prints: replacement source did not produce a normalized real-data CSV
- ohlcv_intraday_bars: replacement source did not produce a normalized real-data CSV
- options_flow_snapshots: replacement source did not produce a normalized real-data CSV
- physical_inventory_sensors: replacement source did not produce a normalized real-data CSV
- vpin_trade_ticks: replacement source did not produce a normalized real-data CSV
- cross_asset_price_ticks/Coinbase public candles: BLOCKED_OR_UNREACHABLE — Coinbase candle replacement source unreachable.
- vpin_trade_ticks/Binance aggTrades public archive: BLOCKED_OR_UNREACHABLE — Binance aggTrades replacement source unreachable.
- options_flow_snapshots/CBOE put-call ratio CSV archives: BLOCKED_OR_UNREACHABLE — CBOE PCR replacement source unreachable or returned no in-range rows.
- dark_pool_block_prints/FINRA Reg SHO daily short-sale files: BLOCKED_OR_UNREACHABLE — FINRA Reg SHO replacement source unreachable.
- cot_positioning/CFTC official COT compressed files: BLOCKED_OR_UNREACHABLE — CFTC COT replacement source unreachable or no mapped rows found.
- physical_inventory_sensors/EIA/FRED official physical-macro proxies: BLOCKED_OR_UNREACHABLE — EIA/FRED replacement sources unavailable or keys missing.

## Source results

| Feed | Replacement source | Status | Rows | Files | Reason |
|---|---|---:|---:|---:|---|
| `cross_asset_price_ticks` | Coinbase public candles | **BLOCKED_OR_UNREACHABLE** | 0 | 0 | Coinbase candle replacement source unreachable.; errors: https://api.exchange.coinbase.com/products/BTC-USD/candles?start=2026-01-01T00%3A00%3A00Z&end=2026-01-01T05%3A59%3A00Z&granularity=60: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://api.exchange.coinbase.com/products/BTC-USD/candles?start=2026-01-01T06%3A00%3A00Z&end=2026-01-01T11%3A59%3A00Z&granularity=60: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://api.exchange.coinbase.com/products/BTC-USD/candles?start=2026-01-01T12%3A00%3A00Z&end=2026-01-01T17%3A59%3A00Z&granularity=60: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992) |
| `vpin_trade_ticks` | Binance aggTrades public archive | **BLOCKED_OR_UNREACHABLE** | 0 | 0 | Binance aggTrades replacement source unreachable.; errors: https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-01-01.zip: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-01-02.zip: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-01-03.zip: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992) |
| `options_flow_snapshots` | CBOE put-call ratio CSV archives | **BLOCKED_OR_UNREACHABLE** | 0 | 0 | CBOE PCR replacement source unreachable or returned no in-range rows.; errors: https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992) |
| `dark_pool_block_prints` | FINRA Reg SHO daily short-sale files | **BLOCKED_OR_UNREACHABLE** | 0 | 0 | FINRA Reg SHO replacement source unreachable.; errors: https://cdn.finra.org/equity/regsho/daily/CNMSshvol20260101.txt: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://cdn.finra.org/equity/regsho/daily/CNMSshvol20260102.txt: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://cdn.finra.org/equity/regsho/daily/CNMSshvol20260103.txt: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992) |
| `cot_positioning` | CFTC official COT compressed files | **BLOCKED_OR_UNREACHABLE** | 0 | 0 | CFTC COT replacement source unreachable or no mapped rows found.; errors: https://www.cftc.gov/files/dea/history/deacot2025.zip: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992); https://www.cftc.gov/files/dea/history/deacot2026.zip: URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992) |
| `physical_inventory_sensors` | EIA/FRED official physical-macro proxies | **BLOCKED_OR_UNREACHABLE** | 0 | 0 | EIA/FRED replacement sources unavailable or keys missing.; errors: EIA: Failed to fetch https://api.eia.gov/v2/electricity/retail-sales/data/?frequency=monthly&data%5B0%5D=sales&facets%5Bsectorid%5D%5B%5D=IND&facets%5Bstateid%5D%5B%5D=US&sort%5B0%5D%5Bcolumn%5D=period&sort%5B0%5D%5Bdirection%5D=desc&offset=0&length=36&api_key=REDACTED: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)>; FRED: Failed to fetch https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&file_type=json&sort_order=desc&limit=260&api_key=REDACTED: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |

## Truth rule

Only rows downloaded from free/public replacement sources are written. Missing feeds remain blocked; no demo or synthetic rows are generated.
