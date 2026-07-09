#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m aduns_fx.cli live --config config/live.example.json "$@"
