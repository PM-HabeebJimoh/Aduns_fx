# HYDRA-PRIME GitHub Feed Run Summary

- Generated at: 2026-07-09T15:36:41Z
- Date range: `2026-01-01` to `2026-07-07`
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
| Free replacement acquisition | 2 | PARTIAL_OR_BLOCKED |
| Strict opportunity audit | 2 | BLOCKED |

## Artifacts

- Live health: `reports/hydra_prime_live_health.json`
- Free replacement probe: `reports/free_source_probe_2026-01-01_to_2026-07-07.md/json`
- Replacement acquisition reports: `reports/hydra_prime_replacement_acquisition_2026-01-01_to_2026-07-07.md/json`
- Opportunity audit reports: `reports/hydra_prime_opportunity_audit_2026-01-01_to_2026-07-07.md/json`
- Alert log: `logs/hydra_prime_alerts.jsonl` if alerts fired

## Truth Rule

If a feed is missing, unreachable, private, restricted, or absent from the manifest, the reports show BLOCKED instead of fabricated opportunities.
