#!/usr/bin/env bash
# Thin LIVE integration lane for matchy: exercises the real api -> service -> repository path against
# a live Teller Postgres DB + a live Mailcart endpoint. Unlike the unit lanes (which stub every
# dependency), this lane only does real work when those services are actually present. It is opt-in
# and dependency-probed so the default parallel suite stays green offline without faking a pass.
umask 007
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]-$0}"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd -P)"
cd "$REPO_ROOT"

VENV_NAME="${VENV_NAME:-matchy-venv}"
if [[ -d "${REPO_ROOT}/${VENV_NAME}/bin" ]]; then
  export PATH="${REPO_ROOT}/${VENV_NAME}/bin:${PATH}"
fi

#R001: Soft-pass (exit 0) with an explicit SKIP message rather than failing or faking a pass. This is
#R001: the only success path when the live Teller DB / Mailcart dependencies are not present, so the
#R001: lane never turns the normal offline suite red and never reports a false green.
skip_soft_pass() {
  echo "⏭️  SKIP (live integration): $1"
  echo "PASS (soft): matchy live integration lane skipped; offline/unit lanes are unaffected."
  exit 0
}

#R010: Gate all live execution behind an explicit opt-in so live services are NEVER required by the
#R010: default discovered suite. Without MATCHY_LIVE_INTEGRATION=true the lane always soft-passes and
#R010: never attempts to reach Postgres/Mailcart or invoke the integration test module.
if [[ "${MATCHY_LIVE_INTEGRATION:-false}" != "true" ]]; then
  skip_soft_pass "opt-in disabled; set MATCHY_LIVE_INTEGRATION=true (with a live Teller DB + Mailcart) to enable."
fi

#R005: Probe both required dependencies and name whichever is unavailable in the skip message so a
#R005: misconfigured live run reports the missing piece instead of erroring deep inside pytest.
missing=()

mailcart_base_url="${MAILCART_SERVICE_BASE_URL:-https://127.0.0.1:8788}"
mailcart_base_url="${mailcart_base_url%/}"
if ! curl -fsS -k --max-time 5 "${mailcart_base_url}/health" >/dev/null 2>&1; then
  missing+=("Mailcart (${mailcart_base_url}/health unreachable)")
fi

db_host="${TELLER_DB_HOST:-127.0.0.1}"
db_port="${TELLER_DB_PORT:-5432}"
if [[ -z "${TELLER_DB_PASSWORD:-}" ]]; then
  missing+=("Teller DB (TELLER_DB_PASSWORD unset)")
elif ! (exec 3<>"/dev/tcp/${db_host}/${db_port}") 2>/dev/null; then
  missing+=("Teller DB (${db_host}:${db_port} not accepting connections)")
fi

if [[ "${#missing[@]}" -gt 0 ]]; then
  skip_soft_pass "missing live dependencies: ${missing[*]}"
fi

#R010: Dependencies present -> run the end-to-end live match scenario, which constructs a real
#R010: MatchService and asserts persisted match results. The integration module lives outside
#R010: tests/py so the offline unit lane (t06) never collects it.
echo "▶ Running matchy LIVE integration tests against Teller DB ${db_host}:${db_port} + ${mailcart_base_url} ..."
exec python3 -m pytest tests/integration -q
