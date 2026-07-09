# HYDRA-PRIME Required Data Acquisition Report

- Requested period: `2026-01-01` to `2026-01-31`
- Data directory: `data/realtime_archive`
- Manifest: `data/realtime_archive/manifest.json`
- Status: **BLOCKED**
- Generated at: `2026-07-09T12:53:24.289592+00:00`

## Blockers

- cot_positioning: not acquired as a verified strict feed
- cross_asset_price_ticks: not acquired as a verified strict feed
- dark_pool_block_prints: not acquired as a verified strict feed
- ohlcv_intraday_bars: not acquired as a verified strict feed
- options_flow_snapshots: not acquired as a verified strict feed
- physical_inventory_sensors: not acquired as a verified strict feed
- vpin_trade_ticks: not acquired as a verified strict feed
- cross_asset_price_ticks/Dukascopy tick archive: UNREACHABLE — Dukascopy public tick archive was unreachable from this sandbox.
- vpin_trade_ticks/Binance public aggTrades archive: UNREACHABLE — All public source download attempts failed or were unreachable from this sandbox.
- options_flow_snapshots/Deribit public options summary: UNREACHABLE — All public source download attempts failed or were unreachable from this sandbox.
- options_flow_snapshots/CBOE daily market statistics: UNREACHABLE — All public source download attempts failed or were unreachable from this sandbox.
- dark_pool_block_prints/FINRA OTC transparency API weekly summary GLD probe: UNREACHABLE — All public source download attempts failed or were unreachable from this sandbox.
- cot_positioning/CFTC 2026 COT historical ZIP: UNREACHABLE — All public source download attempts failed or were unreachable from this sandbox.
- physical_inventory_sensors/LME reports landing page probe: ACCESS_AGREEMENT_OR_MANUAL_EXPORT_REQUIRED — All public source download attempts failed or were unreachable from this sandbox.

## Source Attempts

| Feed | Source | Status | Rows | Files | Reason |
|---|---|---:|---:|---:|---|
| `cross_asset_price_ticks` | Dukascopy tick archive | **UNREACHABLE** | 0 | 0 | Dukascopy public tick archive was unreachable from this sandbox. |
<!-- [{"url": "https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/00/01/00h_ticks.bi5", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}, {"url": "https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/00/01/01h_ticks.bi5", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}, {"url": "https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/00/01/02h_ticks.bi5", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}] -->
| `vpin_trade_ticks` | Binance public aggTrades archive | **UNREACHABLE** | 0 | 0 | All public source download attempts failed or were unreachable from this sandbox. |
<!-- [{"url": "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-01-01.zip", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}, {"url": "https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-01.zip", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}] -->
| `options_flow_snapshots` | Deribit public options summary | **UNREACHABLE** | 0 | 0 | All public source download attempts failed or were unreachable from this sandbox. |
<!-- [{"url": "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}] -->
| `options_flow_snapshots` | CBOE daily market statistics | **UNREACHABLE** | 0 | 0 | All public source download attempts failed or were unreachable from this sandbox. |
<!-- [{"url": "https://www.cboe.com/markets/us/options/market-statistics/daily/", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}] -->
| `dark_pool_block_prints` | FINRA OTC transparency API weekly summary GLD probe | **UNREACHABLE** | 0 | 0 | All public source download attempts failed or were unreachable from this sandbox. |
<!-- [{"url": "https://api.finra.org/data/group/otcMarket/name/weeklySummary", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}] -->
| `cot_positioning` | CFTC 2026 COT historical ZIP | **UNREACHABLE** | 0 | 0 | All public source download attempts failed or were unreachable from this sandbox. |
<!-- [{"url": "https://www.cftc.gov/files/dea/history/deacot2026.zip", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}] -->
| `physical_inventory_sensors` | LME reports landing page probe | **ACCESS_AGREEMENT_OR_MANUAL_EXPORT_REQUIRED** | 0 | 0 | All public source download attempts failed or were unreachable from this sandbox. |
<!-- [{"url": "https://www.lme.com/en/Market-data/Reports-and-data/Warehouse-and-stocks-reports", "error": "URL error: TLS/SSL connection has been closed (EOF) (_ssl.c:992)"}] -->

## Non-negotiable truth

The acquirer does not fabricate data, bypass access controls, or create simulated feeds. Execution has been removed: this system only needs market/opportunity data feeds and never requires broker fill ledgers.
