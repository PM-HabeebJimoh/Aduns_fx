#!/usr/bin/env bash
set -uo pipefail

# GitHub/feed runner for HYDRA-PRIME.
# It never fabricates data. It runs the live feed health check, public acquisition
# attempts, and strict opportunity audit, then writes a summary. By default it
# exits 0 when the software completed even if real feeds are blocked; set
# FAIL_ON_BLOCKED=true to make blocked feeds fail the job.

START_DATE="${START_DATE:-2026-01-01}"
END_DATE="${END_DATE:-2026-01-31}"
DAILY_AUDIT="${DAILY_AUDIT:-false}"
FAIL_ON_BLOCKED="${FAIL_ON_BLOCKED:-false}"
REPORT_DIR="${REPORT_DIR:-reports}"
DATA_DIR="${DATA_DIR:-data/realtime_archive}"
LIVE_CONFIG="${LIVE_CONFIG:-config/live.example.json}"

mkdir -p "$REPORT_DIR" "$DATA_DIR" logs

summary="$REPORT_DIR/github_feed_run_summary.md"

run_step() {
  local name="$1"
  shift
  echo "::group::$name"
  "$@"
  local code=$?
  echo "::endgroup::"
  echo "$code"
}

echo "# HYDRA-PRIME GitHub Feed Run Summary" > "$summary"
echo >> "$summary"
echo "- Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$summary"
echo "- Date range: \`$START_DATE\` to \`$END_DATE\`" >> "$summary"
echo "- Data dir: \`$DATA_DIR\`" >> "$summary"
echo "- Report dir: \`$REPORT_DIR\`" >> "$summary"
echo "- Constraint: real/live archived data only; no demo, no simulation, no assumptions." >> "$summary"
echo "- Output mode: opportunity alerts + advisory execution parameters; no broker execution/order routing/fills." >> "$summary"
echo >> "$summary"
echo "## Step Results" >> "$summary"
echo >> "$summary"
echo "| Step | Exit Code | Meaning |" >> "$summary"
echo "|---|---:|---|" >> "$summary"

set +e
python -m unittest discover -v
TEST_CODE=$?
echo "| Unit tests | $TEST_CODE | $([ $TEST_CODE -eq 0 ] && echo OK || echo FAILED) |" >> "$summary"

python -m aduns_fx.cli live --config "$LIVE_CONFIG" --once
LIVE_CODE=$?
echo "| Live feed health | $LIVE_CODE | $([ $LIVE_CODE -eq 0 ] && echo LIVE || echo NO_LIVE_FEEDS_OR_ERROR) |" >> "$summary"

python -m aduns_fx.cli acquire --start "$START_DATE" --end "$END_DATE" --data-dir "$DATA_DIR" --report-dir "$REPORT_DIR" --timeout 20
ACQUIRE_CODE=$?
echo "| Public feed acquisition | $ACQUIRE_CODE | $([ $ACQUIRE_CODE -eq 0 ] && echo ACQUIRED || echo BLOCKED_OR_UNREACHABLE) |" >> "$summary"

python -m aduns_fx.cli backtest --start "$START_DATE" --end "$END_DATE" --data-dir "$DATA_DIR" --report-dir "$REPORT_DIR"
AUDIT_CODE=$?
echo "| Strict opportunity audit | $AUDIT_CODE | $([ $AUDIT_CODE -eq 0 ] && echo OK || echo BLOCKED) |" >> "$summary"

if [ "$DAILY_AUDIT" = "true" ]; then
  echo >> "$summary"
  echo "## Daily Audit" >> "$summary"
  echo >> "$summary"
  echo "Running per-day strict opportunity audits." >> "$summary"
  mkdir -p "$REPORT_DIR/daily"
  current="$START_DATE"
  while [ "$current" != "$(date -I -d "$END_DATE + 1 day")" ]; do
    python -m aduns_fx.cli backtest --start "$current" --end "$current" --data-dir "$DATA_DIR" --report-dir "$REPORT_DIR/daily" >/tmp/hydra_daily.out 2>&1
    day_code=$?
    echo "- $current: $([ $day_code -eq 0 ] && echo OK || echo BLOCKED) (exit $day_code)" >> "$summary"
    current="$(date -I -d "$current + 1 day")"
  done
fi

cat >> "$summary" <<EOF

## Artifacts

- Live health: \`reports/hydra_prime_live_health.json\`
- Acquisition reports: \`$REPORT_DIR/hydra_prime_acquisition_${START_DATE}_to_${END_DATE}.md/json\`
- Opportunity audit reports: \`$REPORT_DIR/hydra_prime_opportunity_audit_${START_DATE}_to_${END_DATE}.md/json\`
- Alert log: \`logs/hydra_prime_alerts.jsonl\` if alerts fired

## Truth Rule

If a feed is missing, unreachable, private, restricted, or absent from the manifest, the reports show BLOCKED instead of fabricated opportunities.
EOF

cat "$summary"

if [ "$TEST_CODE" -ne 0 ]; then
  exit "$TEST_CODE"
fi

if [ "$FAIL_ON_BLOCKED" = "true" ]; then
  if [ "$LIVE_CODE" -ne 0 ] || [ "$ACQUIRE_CODE" -ne 0 ] || [ "$AUDIT_CODE" -ne 0 ]; then
    exit 2
  fi
fi

exit 0
