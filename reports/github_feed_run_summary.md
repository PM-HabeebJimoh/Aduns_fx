# HYDRA-PRIME GitHub Feed Run Summary

- Generated at: 2026-07-09T14:42:24Z
- Date range: `2026-01-01` to `2026-01-31`
- Data dir: `data/realtime_archive`
- Report dir: `reports`
- Constraint: real/live archived data only; no demo, no simulation, no assumptions.
- Output mode: opportunity alerts + advisory execution parameters; no broker execution/order routing/fills.

## Step Results

| Step | Exit Code | Meaning |
|---|---:|---|
| Unit tests | 0 | OK |
| Live feed health | 2 | NO_LIVE_FEEDS_OR_ERROR |
| Free replacement source probe | 2 | PARTIAL_OR_BLOCKED |
| Public feed acquisition | 2 | BLOCKED_OR_UNREACHABLE |
| Strict opportunity audit | 2 | BLOCKED |

## Artifacts

- Live health: `reports/hydra_prime_live_health.json`
- Free replacement probe: `reports/free_source_probe_2026-01-01_to_2026-01-31.md/json`
- Acquisition reports: `reports/hydra_prime_acquisition_2026-01-01_to_2026-01-31.md/json`
- Opportunity audit reports: `reports/hydra_prime_opportunity_audit_2026-01-01_to_2026-01-31.md/json`
- Alert log: `logs/hydra_prime_alerts.jsonl` if alerts fired

## Truth Rule

If a feed is missing, unreachable, private, restricted, or absent from the manifest, the reports show BLOCKED instead of fabricated opportunities.
