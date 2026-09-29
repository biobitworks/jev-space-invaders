#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT/.private/sponsor-proof/.env"

cd "$ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "SPONSOR_ENV=MISSING"
  echo "RUN=python3 tools/gum_doctor_sponsor/configure_env.py"
  exit 2
fi

chmod 600 "$ENV_FILE"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "SPONSOR_ENV=LOADED"

python3 tools/gum_doctor_sponsor/doctor.py

echo "=== PROVIDER REGISTRY ==="
if python3 -m live_demo.probe_integrations; then
  echo "PROVIDER_PROBE=PASS"
else
  echo "PROVIDER_PROBE=BLOCKED"
fi

echo "GUM_DOCTOR_SPONSOR_RUNNER=PASS"
