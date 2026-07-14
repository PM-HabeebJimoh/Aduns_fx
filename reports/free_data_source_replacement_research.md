# HYDRA-PRIME Free Data Source Replacement Research

Generated: 2026-07-09

Constraint used for this research: **free/public sources only, no demo data, no synthetic data, no simulated data, no assumptions, no illegal bypassing of paywalls or access controls**.

## Executive verdict

Free replacements exist for **most** feed families, but not all replacements are perfect one-for-one equivalents:

- **Best free coverage:** crypto trade ticks/klines, COT, CBOE aggregate put/call ratios, FINRA delayed ATS/OTC and short-sale files, EIA/FRED/USGS macro/physical proxies, LME/CME warehouse reports.
- **Weakest free coverage:** real-time full OPRA options flow/sweeps, real-time dark-pool/block prints, and true centralized trade ticks for spot FX/metals. Those are generally delayed, exchange-specific, proxy-based, or paid/restricted.
- **Practical result:** HYDRA-PRIME can be made live/free with a hybrid stack, but the engine must label each feed as `REAL_TIME`, `DELAYED_OFFICIAL`, `HISTORICAL_ARCHIVE`, or `PROXY` so alerts are honest.

---

## Replacement matrix by required feed

| HYDRA feed | Free replacements | Fit quality | Real-time? | Notes |
|---|---|---:|---:|---|
| `cross_asset_price_ticks` | Dukascopy tick archive for FX/metals/indices; Binance public trades/klines; Coinbase public WebSocket; Kraken public WebSocket; IEX TOPS/DEEP for IEX US equities | High for quote ticks/crypto, medium for equities | Mixed | Dukascopy is quote-tick not consolidated trade tape. Crypto venues provide true trades. IEX is only IEX venue, not full CTA/UTP consolidated tape. |
| `vpin_trade_ticks` | Binance spot/futures `trades`/`aggTrades`; Coinbase `market_trades`; Kraken public time-and-sales | High for crypto only | Yes / archive | True VPIN needs trade sequence + volume + aggressor side. For FX/metals, use a **quote-VPIN proxy** from Dukascopy, not true VPIN. |
| `ohlcv_intraday_bars` | Binance klines; Coinbase candles/WebSocket candles; Kraken OHLC; Dukascopy bars from ticks; Yahoo chart/yfinance; Stooq; Alpha Vantage with limits/entitlements | High | Mixed | Free intraday equities/options often delayed or rate-limited. Binance crypto klines are strongest free archive. |
| `options_flow_snapshots` | Deribit public options summaries + historical options trades; CBOE put/call ratio CSV archives; Yahoo options chain unofficial; Tradier sandbox/delayed; Alpha Vantage options endpoints with free key/limits | Medium | Mostly delayed/current/proxy | No fully free real-time OPRA sweep/flow replacement found. Deribit is excellent for BTC/ETH options. CBOE gives aggregate PCR, not individual flow. |
| `dark_pool_block_prints` | FINRA OTC Transparency Weekly/Monthly/Block Summary APIs; FINRA Reg SHO daily short-sale files; IEX venue last-sale/depth as lit-market supplement | Medium | Delayed | FINRA data is official but delayed/aggregated. Real-time dark-pool prints are not freely available. |
| `cot_positioning` | CFTC official historical compressed files; CFTC PRE/API; open-source `cot_reports` / `cftc-cot`; CotData latest-week free tier | High | Weekly official | This feed is fully replaceable with free official CFTC data. |
| `physical_inventory_sensors` | LME warehouse/stocks reports; CME COMEX warehouse/depository stocks; EIA API; USGS Mineral Commodity Summaries CSV; IMF PortWatch/IEA chokepoint tools; Google Trends via pytrends/Apify | Medium-high | Mixed | Strong official delayed physical data exists. Real-time AIS/port APIs are usually paid; PortWatch/IEA provide usable free delayed/near-real-time macro shipping proxies. |

---

# 1. `cross_asset_price_ticks`

## Recommended free stack

### A. Dukascopy tick archive — FX/metals/indices quote ticks

Use for: `XAUUSD`, `XAGUSD`, `EURUSD`, `GBPUSD`, `USDJPY`, `AUDUSD`, `USDCHF`, some indices and commodities.

Evidence:

- Public discussions document the Dukascopy direct `.bi5` hourly tick URL pattern: `https://datafeed.dukascopy.com/datafeed/{PAIR}/{YEAR}/{MONTH}/{DAY}/{HOUR}h_ticks.bi5`, with zero-indexed months and hourly files [1](https://quant.stackexchange.com/questions/34919/where-can-someone-get-free-or-very-cheap-high-frequency-tick-forex-data), [2](https://www.reddit.com/r/algotrading/comments/65kb14/dukascopy_forex_data/).
- Open-source Dukascopy tooling describes free historical tick/bar access for many instruments, including Forex, commodities, crypto, stocks, ETFs, bonds and indices [5](https://github.com/theorycraft-trading/dukascopy).

Strict label: `HISTORICAL_QUOTE_TICK_ARCHIVE`.

Caveat: not centralized trade prints; use for quote pressure and intraday bars.

### B. Binance public data — crypto leaders and PAXG/BTC proxies

Use for: `BTC`, `ETH`, `PAXG`, crypto risk lead, crypto VPIN, crypto OHLCV.

Evidence:

- Binance states its public data site provides daily/monthly downloadable market data; supports all symbols; daily data becomes available the next day and monthly data at the first Monday of the month [1](https://github.com/binance/binance-public-data/blob/master/README.md).
- Binance public data includes spot `aggTrades`, `trades`, and `klines`; kline intervals include `1s`, `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, and more [1](https://github.com/binance/binance-public-data/blob/master/README.md).

Strict label: `REAL_EXCHANGE_TRADE_ARCHIVE` and `REAL_EXCHANGE_OHLCV_ARCHIVE`.

### C. Coinbase public WebSocket — crypto real-time trades/order book/candles

Use for: alternative BTC/ETH real-time feed; redundancy if Binance blocked.

Evidence:

- Coinbase Advanced Trade WebSocket documents public channels with no authentication, including `ticker`, `market_trades`, `level2`, `candles`, `status`, and `heartbeats` [1](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/websocket).
- Coinbase Exchange WebSocket level2 channel provides order book snapshots and updates without authentication [2](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels).

Strict label: `REAL_TIME_PUBLIC_EXCHANGE_STREAM`.

### D. Kraken public WebSocket — crypto trades/order book

Use for: alternative crypto trades/order book.

Evidence:

- Kraken says authentication is not required for public market data feeds; private feeds require a token [1](https://support.kraken.com/articles/360022326871-kraken-websocket-api-frequently-asked-questions).
- Kraken describes public unauthenticated WebSocket market-data feeds for real-time ticker, time-and-sales, and order book data [4](https://support.kraken.com/articles/360022327631-websocket-api-v1-market-data-feed-example).

Strict label: `REAL_TIME_PUBLIC_EXCHANGE_STREAM`.

### E. IEX TOPS/DEEP — lit US equity venue proxy

Use for: lit-market ETF proxy (`GLD`, `IAU`, `SLV`) when full consolidated equity tape is not free.

Evidence:

- IEX announced DEEP as a free exchange market-data product, but consuming DEEP requires IEX data agreements/forms [2](https://iextrading.com/trading/alerts/2017/011/).
- IEX DEEP provides aggregated real-time depth-of-book quotes and last trade price/size information [3](https://addisonlynch.github.io/iexfinance/stable/iexdata.html).

Strict label: `REAL_TIME_LIT_VENUE_PROXY`.

Caveat: IEX only, not consolidated CTA/UTP.

---

# 2. `vpin_trade_ticks`

## Recommended free stack

### A. True VPIN for crypto: Binance + Coinbase + Kraken

- Binance public `trades` and `aggTrades` include price, quantity, timestamp, and buyer-maker side fields [1](https://github.com/binance/binance-public-data/blob/master/README.md).
- Coinbase `market_trades` public channel provides real-time market trade updates without authentication [1](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/websocket).
- Kraken public WebSocket provides unauthenticated time-and-sales market data [4](https://support.kraken.com/articles/360022327631-websocket-api-v1-market-data-feed-example).

Strict label: `TRUE_VPIN_AVAILABLE_FOR_CRYPTO`.

### B. Quote-VPIN proxy for FX/metals: Dukascopy

Use Dukascopy bid/ask quote ticks and quote volumes to estimate imbalance. This is **not true VPIN** because spot FX/metals do not have a free centralized public trade tape.

Strict label: `QUOTE_TOXICITY_PROXY_NOT_TRUE_VPIN`.

Hard truth: no free, public, centralized true trade-tick tape for spot FX/metals was identified.

---

# 3. `ohlcv_intraday_bars`

## Recommended free stack

### A. Binance klines

Use for crypto leaders and tokenized gold proxies.

Evidence: Binance public data includes `klines` from `/api/v3/klines`, supports all symbols, and intervals from `1s` and `1m` through higher timeframes [1](https://github.com/binance/binance-public-data/blob/master/README.md).

### B. Dukascopy tick-to-bar resampling

Use for FX/metals. Decode `.bi5` quote ticks and resample to 1m/5m OHLCV.

Evidence: Dukascopy direct tick URL and binary layout are documented by community reverse engineering [1](https://quant.stackexchange.com/questions/34919/where-can-someone-get-free-or-very-cheap-high-frequency-tick-forex-data), [2](https://www.reddit.com/r/algotrading/comments/65kb14/dukascopy_forex_data/).

### C. Coinbase/Kraken candles

Use for crypto redundancy. Coinbase lists `candles` as a public no-auth WebSocket channel [1](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/websocket). Kraken public WebSocket/REST can provide market data without authentication [1](https://support.kraken.com/articles/360022326871-kraken-websocket-api-frequently-asked-questions).

### D. Yahoo/Stooq/Alpha Vantage as fallback, not primary strict feed

- Yahoo Finance has no official public API; yfinance/yahoo-finance2 use unofficial access and can fetch OHLCV/options data [1](https://publicapis.io/blog/yahoo-finance-api-guide).
- Stooq provides broad OHLCV downloads and some 5-minute/hourly datasets, but no official API [2](https://www.quantstart.com/articles/an-introduction-to-stooq-pricing-data/).
- Alpha Vantage offers free APIs broadly, but its documentation also labels the intraday endpoint as premium for realtime/15-minute delayed/historical intraday access [1](https://www.alphavantage.co/documentation/).

Strict label: `FALLBACK_DELAYED_OR_UNOFFICIAL`.

---

# 4. `options_flow_snapshots`

## Recommended free stack

### A. Deribit public BTC/ETH options

Use for BTC/ETH options flow, skew, OTM volume, risk-reversal proxy and crypto-to-gold risk proxy.

Evidence:

- Deribit `get_last_trades_by_currency_and_time` retrieves trades in a currency within a time range with price, amount, direction, timestamp and trade ID [3](https://docs.deribit.com/api-reference/market-data/public-get_last_trades_by_currency_and_time).
- Deribit examples show public option trade history including IV, mark price, direction, amount, instrument name and index price [2](https://questdb.com/blog/analyzing-bitcoin-options-data/).

Strict label: `REAL_EXCHANGE_OPTIONS_FLOW_CRYPTO`.

### B. CBOE aggregate put/call ratio CSV archives

Use for broad equity/index option sentiment, not individual flow/sweeps.

Evidence:

- CBOE publishes daily market statistics with put/call ratios [1](https://www.cboe.com/markets/us/options/market-statistics/daily/).
- CBOE provides CSV archives for equity put/call ratios [3](https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv) and index put/call ratio archives [5](https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv).

Strict label: `OFFICIAL_AGGREGATE_OPTIONS_SENTIMENT`.

### C. Tradier / Yahoo / Alpha Vantage as delayed or limited fallbacks

- Tradier sandbox/free developer access can provide delayed options market data, while real-time requires brokerage/account access [1](https://techbum.io/best-free-api-for-stock-market-data), [4](https://zorro-project.com/manual/en/tradier.htm).
- Yahoo options chain data is accessible through unofficial libraries, but Yahoo does not offer an official public API [1](https://publicapis.io/blog/yahoo-finance-api-guide), [2](https://jsr.io/@gadicc/yahoo-finance2/doc/modules/options).
- Alpha Vantage documents US options data APIs and free key access, but entitlement/rate limits must be verified for the specific endpoint [1](https://www.alphavantage.co/documentation/).

Strict label: `DELAYED_OR_UNOFFICIAL_OPTIONS_CHAIN_PROXY`.

Hard truth: no free full real-time OPRA unusual-options-flow/sweep feed was found.

---

# 5. `dark_pool_block_prints`

## Recommended free stack

### A. FINRA OTC Transparency API — ATS/OTC weekly/monthly/block summaries

Use for dark-pool/ATS/block footprint with publication delay.

Evidence:

- FINRA developer documentation lists `OTCMARKET / WEEKLYSUMMARY` fields including issue symbol, firm, MPID, market participant, total weekly trade count/share quantity, summary type, week start, and publication dates [1](https://developer.finra.org/docs).
- FINRA catalog includes Blocks Summary, OTC Block Summary, Weekly Summary, Monthly Summary, and Reg SHO Daily Short Sale Volume datasets [3](https://developer.finra.org/catalog).
- FINRA introduced historical API support for OTC Transparency Weekly Summary through `WeeklySummaryHistoric` [5](https://www.finra.org/filing-reporting/otc-transparency/otc-transparency-api-changes).

Strict label: `OFFICIAL_DELAYED_ATS_OTC_BLOCK_DATA`.

### B. FINRA Reg SHO Daily Short Sale Volume files

Use for short-pressure and squeeze setup features.

Evidence:

- FINRA short-sale daily files are available through URL patterns such as `https://cdn.finra.org/equity/regsho/daily/CNMSshvolYYYYMMDD.txt` and related market-center files [2](https://mengjiexu.com/post/collect-daily-level-short-selling-data-with-no-costs-and-no-delay/).
- FINRA documentation states Short Sale Volume data can be exported and is also available via API for automation [5](https://www.finra.org/sites/default/files/2020-12/short-sale-volume-user-guide.pdf).

Strict label: `OFFICIAL_DAILY_SHORT_SALE_VOLUME`.

Hard truth: real-time dark-pool prints are not free. FINRA sources are delayed and aggregated, but official.

---

# 6. `cot_positioning`

## Recommended free stack

### A. Official CFTC historical compressed files

Use for weekly positioning by instrument.

Evidence:

- CFTC historical compressed report URLs such as `https://www.cftc.gov/files/dea/history/deacot2010.zip` are documented in COT tooling/tutorials [2](https://www.mql5.com/en/articles/34).
- Open-source libraries download official CFTC COT archives and support report types including legacy, disaggregated, and traders-in-financial-futures [4](https://github.com/NDelventhal/cot_reports), [1](https://github.com/Mcamin/cftc-cot).

Strict label: `OFFICIAL_WEEKLY_POSITIONING`.

### B. CFTC API / third-party wrappers

- COTData has a free tier for latest-week COT data, with paid history [2](https://www.cotdata.net/api-access).
- Public CFTC API scrapers exist and describe the CFTC data as public/free [2](https://www.cotdata.net/api-access), [2](https://apify.com/jungle_synthesizer/cftc-cot-positions-scraper).

Strict label: `OFFICIAL_OR_PUBLIC_DOMAIN_WEEKLY_POSITIONING`.

This feed is fully replaceable for free.

---

# 7. `physical_inventory_sensors`

## Recommended free stack

### A. LME warehouse and stock reports

Use for live/cancelled warrants and warehouse stocks for industrial metals.

Evidence:

- LME warehouse/stock reports include stock movement, opening stocks, open and cancelled tonnage, delivered in/out tonnage by metal/location/country; daily two-day-delayed Excel reports are available on LME.com [3](https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports).
- LME says off-warrant stock data began daily publication/download from April 2025 via OLP, with monthly reports on LME.com [5](https://www.lme.com/en/news/press-releases/2025/lme-provides-daily-insight-into-off-warrant-stocks).
- Reuters/TradingView reporting says prior-day off-warrant data is subscription based, while a free version is delayed by three days on the LME website [1](https://www.tradingview.com/news/reuters.com,2025:newsml_L8N3Q017E:0-lme-warehouses-to-report-off-warrant-metal-stocks-daily-from-april/).

Strict label: `OFFICIAL_DELAYED_PHYSICAL_METAL_STOCKS`.

### B. CME/COMEX warehouse and delivery stocks

Use for gold/silver/copper/platinum/palladium inventory.

Evidence:

- CME Group has COMEX/NYMEX delivery notices and warehouse/depository stocks for gold, silver, copper, platinum and palladium [2](https://www.cmegroup.com/solutions/clearing/operations-and-deliveries/nymex-delivery-notices.html).
- Third-party dashboards state they source daily COMEX inventory data from official CME Group warehouse reports [1](https://www.thevaultreport.com/comex), [3](https://metalcharts.org/comex/inventory).

Strict label: `OFFICIAL_OR_DERIVED_DAILY_COMEX_STOCKS`.

### C. EIA API — electricity/energy demand proxies

Use for industrial power demand, energy activity, and commodity demand pressure.

Evidence:

- EIA states its open data is available through a free API and includes electricity, petroleum, natural gas, etc. [5](https://www.eia.gov/opendata/).
- EIA electricity routes include retail sales and electric power operational data, including daily/hourly operations [1](https://ramikrispin.github.io/EIAapi/articles/intro.html).
- EIA documentation shows electricity retail sales include sales, revenue, price and customers, with metadata available through the API [3](https://www.eia.gov/opendata/documentation.php).

Strict label: `OFFICIAL_ENERGY_DEMAND_PROXY`.

### D. USGS Mineral Commodity Summaries

Use for annual/quarterly physical production and supply-demand context.

Evidence:

- USGS Mineral Commodity Summaries 2025 database contains U.S. salient statistics and world production statistics for 90+ nonfuel mineral commodities, with CSV table files [3](https://www.usgs.gov/publications/mineral-commodity-summaries-2025).

Strict label: `OFFICIAL_LOW_FREQUENCY_SUPPLY_CONTEXT`.

### E. Port/shipping congestion: IMF PortWatch / IEA tools / AIS free front-ends

Use for macro shipping disruption proxies.

Evidence:

- IMF PortWatch-based analysis describes weekly port congestion indicators such as dwell times and anchorage queues, and notes AIS limitations [1](https://content.ballastmarkets.com/blog/2024-11-05-imf-portwatch-changed-forecasting/).
- IEA’s chokepoint tool draws on IMF PortWatch and UN Global Platform data for shipping flows through key chokepoints [3](https://www.iea.org/data-and-statistics/data-tools/middle-east-maritime-chokepoints-shipping-monitor).
- Some AIS tools advertise free live tracking and voyage-history playback, but production-grade API/export usually requires paid services [1](https://aisvesseltracker.com/), [2](https://www.avsglobalsupply.com/blog-detail/marinetraffic).

Strict label: `FREE_SHIPPING_PROXY_OR_LIMITED_AIS`.

### F. Google Trends

Use for retail demand proxy, e.g., `buy gold`, `gold price`, `silver squeeze`.

Evidence:

- Google Trends has no official public API, but pytrends is an unofficial Python client for retrieving Trends data [2](https://www.premiumleads.com/en/blog/seo/how-to-get-google-trends-data-with-pytrends-and-python/).
- Apify offers an unofficial Google Trends API with a free starter allowance [1](https://apify.com/api/google-trends/python).

Strict label: `UNOFFICIAL_RETAIL_ATTENTION_PROXY`.

---

## Free replacement architecture

### Tier 1 — real-time/free streams

- Coinbase public WebSocket: crypto trades, ticker, candles, level2.
- Kraken public WebSocket: crypto trades, ticker, order book.
- Binance public API/WebSocket: crypto trades and klines.
- IEX DEEP/TOPS: IEX lit equity venue proxy after required free data agreements.

### Tier 2 — official delayed free data

- FINRA OTC Transparency / Reg SHO.
- CBOE PCR CSV archives.
- CFTC COT official archives/API.
- LME two-day delayed warehouse reports.
- CME warehouse/depository reports.
- EIA/FRED/USGS official macro/physical data.

### Tier 3 — proxy/unofficial free data

- Dukascopy quote ticks for spot FX/metals.
- Yahoo/yfinance options and OHLCV fallback.
- Google Trends/pytrends.
- PortWatch/IEA/AIS dashboards as shipping disruption proxy.

---

## Implementation priority for HYDRA-PRIME

1. **Add Coinbase and Kraken live WebSocket collectors** for crypto trade/leader redundancy.
2. **Improve Binance archive downloader** with retry/CDN mirror logic and futures support.
3. **Keep Dukascopy for FX/metals quote ticks**, but label it quote-based, not true trades.
4. **Add CBOE PCR CSV loader** for historical aggregate options sentiment.
5. **Add Deribit historical options trade loader** for BTC/ETH options flow.
6. **Add FINRA OTC + Reg SHO loaders** for delayed dark-pool/short-pressure footprints.
7. **Add CFTC COT loader** using direct ZIP and CFTC API fallback.
8. **Add physical loaders:** LME Excel scraper/export parser, CME warehouse parser, EIA API, USGS CSV, FRED rates, PortWatch/IEA shipping proxies, Google Trends proxy.
9. **Tag every signal input with provenance:** `REAL_TIME`, `DELAYED_OFFICIAL`, `HISTORICAL_ARCHIVE`, `UNOFFICIAL`, `PROXY`.

---

## Hard truth

A 100% free, real-time, all-asset, all-signal replacement stack does **not** exist. The closest truthful free stack is:

- Real-time where free venues allow it: crypto and some lit-equity venue data.
- Delayed official data for FINRA, LME, CBOE, COT and physical warehouse reports.
- Proxy data for FX/metals tick pressure, retail demand, and shipping congestion.

HYDRA-PRIME can still run as a free opportunity engine, but alerts must disclose feed provenance and delay status.
