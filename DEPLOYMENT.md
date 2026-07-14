# HYDRA-PRIME Live Deployment

HYDRA-PRIME is deployed as an **opportunity alert service**.

It detects high-conviction pre-movement opportunities and emits alerts with advisory trade parameters. It does **not** place trades, route orders, connect to brokers, or simulate fills.

## Live output

Each alert includes:

- instrument
- long/short bias
- opportunity score
- expected movement window
- agreeing independent signal count
- fired signal details
- leverage
- notional
- risk %
- max loss
- stop loss
- take profit
- units, when a reference price is available

## Local live run

Run one live health/scan cycle:

```bash
python -m aduns_fx.cli live --config config/live.example.json --once
```

Run continuously:

```bash
python -m aduns_fx.cli live --config config/live.example.json
```

Or:

```bash
./scripts/run_live.sh
```

## Docker deployment

Build and run:

```bash
docker compose up --build -d
```

View logs:

```bash
docker compose logs -f hydra-prime-live
```

Stop:

```bash
docker compose down
```

## Alert log and health report

Default files:

```text
logs/hydra_prime_alerts.jsonl
reports/hydra_prime_live_health.json
```

The health report contains:

- feed status
- loaded row counts
- active signal counts
- current opportunity alerts
- output mode flags proving no broker execution/order routing/simulated fills

## Webhook alerts

Set this environment variable to receive JSON alert payloads:

```bash
export HYDRA_ALERT_WEBHOOK_URL="https://your-webhook-endpoint.example/alerts"
```

Docker Compose also reads `HYDRA_ALERT_WEBHOOK_URL` from the environment.

## Required network/data access

The live scanner currently attempts:

- Yahoo chart endpoint for market OHLCV/leader context
- Binance public API for BTC/PAXG prices and aggregate trades
- Deribit public API for options snapshots

A production-grade deployment should add authenticated/vendor feeds for:

- full real-time cross-asset ticks
- true trade ticks for VPIN on traded venues
- historical/live options flow snapshots
- dark-pool/block prints
- COT scheduled archive loader
- physical inventory/cancelled-warrant sensors

## Current sandbox limitation

In the Arena sandbox, direct Python/curl HTTPS requests to multiple public data hosts returned TLS/EOF errors during testing. That means the service code is deployed and runnable, but the sandbox network may prevent it from becoming fully live here. Run the same deployment on a server/VPS with normal outbound HTTPS access for live operation.

## No execution boundary

HYDRA-PRIME never sends orders. Advisory trade parameters in alerts are informational only. Execution remains manual/external.
