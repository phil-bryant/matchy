#!/usr/bin/env bats

setup() {
  #R001: Test harness setup for generate_supply_chain_artifacts contract checks.
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd -P)"
  SHIM="${REPO_ROOT}/src/scripts/security/generate_supply_chain_artifacts.py"
}

@test "resolves runner generator path from repo root" {
  #R001-T01: Verify shim source resolves repo root from Path(__file__) and references runner generator path.
  run rg -F "Path(__file__).resolve().parents[3]" "${SHIM}"
  [ "$status" -eq 0 ]
  run rg -F 'repo_root.parent / "runner" / "src" / "scripts" / "security" / "generate_supply_chain_artifacts.py"' "${SHIM}"
  [ "$status" -eq 0 ]
}

@test "has explicit missing-runner failure path" {
  #R005-T01: Verify shim source checks runner_script existence and emits explicit missing-runner error text.
  run rg -F "if not runner_script.is_file():" "${SHIM}"
  [ "$status" -eq 0 ]
  run rg -F 'Missing runner supply-chain generator' "${SHIM}"
  [ "$status" -eq 0 ]
}

@test "forwards argv and executes runner script as __main__" {
  #R010-T01: Verify shim source rewrites sys.argv and invokes runpy.run_path with run_name="__main__".
  run rg -F "sys.argv = [str(runner_script), *sys.argv[1:]]" "${SHIM}"
  [ "$status" -eq 0 ]
  run rg -F 'runpy.run_path(str(runner_script), run_name="__main__")' "${SHIM}"
  [ "$status" -eq 0 ]
}
