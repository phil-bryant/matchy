#!/usr/bin/env bats

setup() {
  #R001: Test harness setup for offline pointer-contract checks.
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd -P)"
  POINTER="${REPO_ROOT}/03_prepare_supply_chain_integrity.sh"
}

@test "centralizes umask/strict mode via the shared pointer shim" {
  #R001-T01: Verify the pointer sources pointer_shim.sh.
  run grep "pointer_shim.sh" "$POINTER"
  [ "$status" -eq 0 ]
}

@test "resolves the shim from the runner src/scripts tree" {
  #R005-T01: Verify the pointer locates the shim under runner/src/scripts.
  run grep "runner/src/scripts" "$POINTER"
  [ "$status" -eq 0 ]
}

@test "selects its runbook profile explicitly before delegation" {
  #R010-T01: Verify the pointer sets RUNBOOK_PROFILE to the repo profile.
  run grep 'RUNBOOK_PROFILE="matchy"' "$POINTER"
  [ "$status" -eq 0 ]
}

@test "delegates to the mapped runner golden" {
  #R015-T01: Verify the pointer calls delegate_golden "03_prepare_supply_chain_integrity.sh" with "$@".
  run grep 'delegate_golden "03_prepare_supply_chain_integrity.sh" "$@"' "$POINTER"
  [ "$status" -eq 0 ]
}
