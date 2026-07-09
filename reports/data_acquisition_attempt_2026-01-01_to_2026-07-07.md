# HYDRA-PRIME Data Acquisition Attempt — 2026-01-01 to 2026-07-07

## User constraint

- Real data only
- Real-time/archive provenance only
- No demo data
- No synthetic/generated/mock/fixture data
- No simulated fills
- No assumptions

## Acquisition status

**FAILED / BLOCKED** for a complete strict backtest dataset.

The runner requires all eight feed files plus actual execution fills. Public crawling cannot lawfully obtain private broker fills or restricted/professional data products. The repository still has no complete verified real-time archive for the requested period.

## Direct download attempts from sandbox

The sandbox attempted direct public HTTP/HTTPS downloads/checks for representative public sources. The local runtime could not establish usable HTTP/TLS sessions to these hosts:

```text
https://api.binance.com/api/v3/time
  -> urllib.error.URLError: TLS/SSL connection closed EOF

https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-01.zip
  -> curl: OpenSSL SSL_connect: SSL_ERROR_SYSCALL
  -> urllib.error.URLError: TLS/SSL connection closed EOF

https://www.cftc.gov/files/dea/history/deacot2026.zip
  -> curl: OpenSSL SSL_connect: SSL_ERROR_SYSCALL
  -> urllib.error.URLError: TLS/SSL connection closed EOF

https://query1.finance.yahoo.com/v8/finance/chart/GC=F?period1=1767225600&period2=1783555200&interval=1d
  -> curl: OpenSSL SSL_connect: SSL_ERROR_SYSCALL
  -> urllib.error.URLError: TLS/SSL connection closed EOF
```

The web-search/fetch tools can see some public pages, but they do not provide a lawful complete bulk download of every required real-time feed plus private fills.

## Feed-by-feed outcome

| Required feed | Public crawl outcome | Strict status |
|---|---|---|
| `cross_asset_price_ticks` | Partial public sources exist for some assets, but not a complete archived tick/<=1m real-time package for all required instruments in this repo. | Missing |
| `vpin_trade_ticks` | Binance can provide crypto trades publicly, but VPIN for XAUUSD/FX/metals requires actual trade-tick stream for those venues. | Missing |
| `ohlcv_intraday_bars` | Public historical bars may exist, but no verified archived real-time feed package is present. | Missing |
| `options_flow_snapshots` | CBOE/Deribit public data is partial/current/proxy; complete historical options-flow snapshots for all days are not present. | Missing |
| `dark_pool_block_prints` | FINRA transparency data exists, but bulk/professional API data is access-controlled and not a complete unauthenticated crawl source. | Missing |
| `cot_positioning` | CFTC public COT exists, but direct download failed in sandbox and it is only one feed family. | Missing |
| `physical_inventory_sensors` | LME/warehouse/off-warrant/cancelled-warrant data is not available here as a complete unauthenticated historical archive. | Missing |
| `actual_execution_fills` | Private broker/exchange ledger. Cannot be crawled publicly or lawfully obtained without account export. | Missing / impossible to public-crawl |

## Backtest rerun

Command:

```bash
python -m aduns_fx.cli backtest --start 2026-01-01 --end 2026-07-07 --data-dir data/realtime_archive --report-dir reports
```

Result:

```text
Status: BLOCKED
EXIT_CODE:2
```

Main report:

```text
reports/hydra_prime_strict_backtest_2026-01-01_to_2026-07-07.md
```

## Truthful conclusion

A complete no-simulation, real-time-only HYDRA-PRIME backtest cannot be produced from public crawling alone. The missing private/restricted files must be supplied or the constraint must be relaxed to allow a historical-market-data simulated backtest.
