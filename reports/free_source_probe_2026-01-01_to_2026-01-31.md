# HYDRA-PRIME Free Replacement Source Probe

- Generated: `2026-07-09T14:42:26.918929+00:00`
- Range: `2026-01-01` to `2026-01-31`
- Status: **PARTIAL_OR_BLOCKED**

| Feed | Source | Status | Provenance | Realtime | Bytes | Reason |
|---|---|---:|---|---:|---:|---|
| `cross_asset_price_ticks` | Dukascopy XAUUSD quote ticks | **BLOCKED_OR_UNREACHABLE** | `HISTORICAL_QUOTE_TICK_ARCHIVE` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `cross_asset_price_ticks` | Binance BTCUSDT latest price | **BLOCKED_OR_UNREACHABLE** | `REAL_TIME_PUBLIC_EXCHANGE_REST` | True | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `cross_asset_price_ticks` | Coinbase BTC-USD ticker | **BLOCKED_OR_UNREACHABLE** | `REAL_TIME_PUBLIC_EXCHANGE_REST` | True | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `cross_asset_price_ticks` | Kraken BTC/USD ticker | **BLOCKED_OR_UNREACHABLE** | `REAL_TIME_PUBLIC_EXCHANGE_REST` | True | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `vpin_trade_ticks` | Binance BTCUSDT aggTrades archive probe | **BLOCKED_OR_UNREACHABLE** | `TRUE_VPIN_AVAILABLE_FOR_CRYPTO` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `vpin_trade_ticks` | Coinbase BTC-USD trades | **BLOCKED_OR_UNREACHABLE** | `TRUE_VPIN_AVAILABLE_FOR_CRYPTO` | True | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `vpin_trade_ticks` | Kraken BTC/USD trades | **BLOCKED_OR_UNREACHABLE** | `TRUE_VPIN_AVAILABLE_FOR_CRYPTO` | True | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `ohlcv_intraday_bars` | Binance BTCUSDT 1m kline archive probe | **BLOCKED_OR_UNREACHABLE** | `REAL_EXCHANGE_OHLCV_ARCHIVE` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `ohlcv_intraday_bars` | Coinbase BTC-USD candles | **BLOCKED_OR_UNREACHABLE** | `REAL_TIME_PUBLIC_EXCHANGE_REST` | True | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `ohlcv_intraday_bars` | Kraken BTC/USD OHLC | **BLOCKED_OR_UNREACHABLE** | `REAL_TIME_PUBLIC_EXCHANGE_REST` | True | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `options_flow_snapshots` | Deribit BTC historical option trades | **BLOCKED_OR_UNREACHABLE** | `REAL_EXCHANGE_OPTIONS_FLOW_CRYPTO` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `options_flow_snapshots` | CBOE equity put-call ratio CSV | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_AGGREGATE_OPTIONS_SENTIMENT` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `options_flow_snapshots` | CBOE index put-call ratio CSV | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_AGGREGATE_OPTIONS_SENTIMENT` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `dark_pool_block_prints` | FINRA Reg SHO CNMS daily short volume | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_DAILY_SHORT_SALE_VOLUME` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `dark_pool_block_prints` | FINRA OTC weekly summary GLD | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_DELAYED_ATS_OTC_BLOCK_DATA` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `cot_positioning` | CFTC legacy COT compressed file | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_WEEKLY_POSITIONING` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `cot_positioning` | CFTC disaggregated COT compressed file | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_WEEKLY_POSITIONING` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `physical_inventory_sensors` | LME warehouse and stock reports page | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_DELAYED_PHYSICAL_METAL_STOCKS` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `physical_inventory_sensors` | CME COMEX delivery notices and stocks page | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_OR_DERIVED_DAILY_COMEX_STOCKS` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `physical_inventory_sensors` | EIA electricity retail sales metadata | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_ENERGY_DEMAND_PROXY` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `physical_inventory_sensors` | FRED real yield DFII10 | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_MACRO_REAL_YIELD_PROXY` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |
| `physical_inventory_sensors` | USGS Mineral Commodity Summaries 2025 page | **BLOCKED_OR_UNREACHABLE** | `OFFICIAL_LOW_FREQUENCY_SUPPLY_CONTEXT` | False | 0 | Could not retrieve source without fabrication. Error: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)> |

## Truth rule

A failed probe means the source was not available from the current runtime; it is not replaced with demo/synthetic data.
