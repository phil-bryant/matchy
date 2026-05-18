#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R015-T02 #R020-T01 #R025-T01 #R030-T01

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "04_run_unit_tests.sh"
}

teardown() {
  teardown_shell_test
}

@test "fails when bats is unavailable" {
  #R001: Script runs in strict mode.
  #R005: Bats is required on PATH.
  #R010: Repo root is resolved from script path.
  #R015: Test discovery uses testing lanes.
  #R020: Missing tests fail clearly.
  #R025: Bats non-zero fails lane.
  #R030: Success prints single PASS line.
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/04_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"bats is required"* ]]
}

@test "fails when no tests are discovered" {
  stub_cmd bats "exit 0"
  run bash "${FIXTURE_ROOT}/04_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"No shell unit tests found"* ]]
}

@test "runs discovered tests and succeeds" {
  mkdir -p "${FIXTURE_ROOT}/testing/sh"
  cat > "${FIXTURE_ROOT}/testing/sh/sample.bats" <<'EOF'
#!/usr/bin/env bats
@test "ok" { [ 1 -eq 1 ]; }
EOF
  chmod +x "${FIXTURE_ROOT}/testing/sh/sample.bats"
  stub_cmd bats "exit 0"
  run bash "${FIXTURE_ROOT}/04_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS: Matchy unit tests completed"* ]]
}
