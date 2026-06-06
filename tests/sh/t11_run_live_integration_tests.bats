#!/usr/bin/env bats
# Contract tests for the opt-in matchy LIVE integration lane (tests/t11_run_live_integration_tests.sh).
# These run fully offline: they assert the lane's skip/probe/opt-in behavior, never live services.

#R001: Bats setup resolves repo root and pointer path for offline pointer-contract tests.
setup() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd -P)"
  LANE="${REPO_ROOT}/tests/t11_run_live_integration_tests.sh"
}

@test "soft-passes with a SKIP message when live deps are absent" {
  #R001-T01: no opt-in -> explicit SKIP and exit 0 (no faked pass, no red suite).
  run env -u MATCHY_LIVE_INTEGRATION "$LANE"
  [ "$status" -eq 0 ]
  [[ "$output" == *"SKIP (live integration)"* ]]
  [[ "$output" == *"PASS (soft)"* ]]
}

@test "names the missing dependency when opt-in is on but deps unreachable" {
  #R005-T01: opt-in on + unreachable deps -> skip message names Mailcart and Teller DB, exit 0.
  run env MATCHY_LIVE_INTEGRATION=true MAILCART_SERVICE_BASE_URL="https://127.0.0.1:9" TELLER_DB_PASSWORD="" "$LANE"
  [ "$status" -eq 0 ]
  [[ "$output" == *"missing live dependencies"* ]]
  [[ "$output" == *"Mailcart"* ]]
  [[ "$output" == *"Teller DB"* ]]
}

@test "does not invoke the live integration module without the opt-in" {
  #R010-T01: without the opt-in the lane reports it is disabled and never runs the integration module.
  run env -u MATCHY_LIVE_INTEGRATION "$LANE"
  [ "$status" -eq 0 ]
  [[ "$output" == *"opt-in disabled"* ]]
  [[ "$output" != *"Running matchy LIVE integration"* ]]
}
