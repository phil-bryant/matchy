#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R015-T02 #R020-T01 #R025-T01 #R030-T01 #R035-T01 #R035-T02 #R040-T01 #R045-T01

load "helpers/common.bash"

make_venv_python_stub() {
  local pytest_exit_code="${1:-0}"
  local bats_exit_code="${2:-0}"
  mkdir -p "${FIXTURE_ROOT}/matchy-venv/bin" "${FIXTURE_ROOT}/testing/py" "${FIXTURE_ROOT}/testing/sh"
  cat > "${FIXTURE_ROOT}/testing/py/sample_test.py" <<'EOF'
def test_ok():
    assert True
EOF
  cat > "${FIXTURE_ROOT}/matchy-venv/bin/python" <<EOF
#!/usr/bin/env bash
if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "pytest" ]; then
  echo "pytest \$*" >> "${CALLS_LOG}"
  if [ "\${3:-}" = "--version" ]; then
    echo "pytest 8.0.0"
    exit 0
  fi
  exit ${pytest_exit_code}
fi
echo "python \$*" >> "${CALLS_LOG}"
exit 0
EOF
  chmod +x "${FIXTURE_ROOT}/matchy-venv/bin/python"
  cat > "${STUB_BIN}/bats" <<EOF
#!/usr/bin/env bash
echo "bats \$*" >> "${CALLS_LOG}"
exit ${bats_exit_code}
EOF
  chmod +x "${STUB_BIN}/bats"
  : > "${CALLS_LOG}"
}

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "05_run_unit_tests.sh"
  make_venv_python_stub 0 0
}

teardown() {
  teardown_shell_test
}

@test "fails when matchy-venv python is unavailable" {
  #R035-T01: Missing venv python fails with explicit guidance.
  rm -rf "${FIXTURE_ROOT}/matchy-venv"
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"matchy-venv python is required"* ]]
}

@test "fails when pytest is unavailable in matchy-venv" {
  #R035-T02: Missing pytest in venv fails with explicit guidance.
  mkdir -p "${FIXTURE_ROOT}/matchy-venv/bin"
  cat > "${FIXTURE_ROOT}/matchy-venv/bin/python" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pytest" ] && [ "${3:-}" = "--version" ]; then
  exit 1
fi
exit 0
EOF
  chmod +x "${FIXTURE_ROOT}/matchy-venv/bin/python"
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"pytest is required in matchy-venv"* ]]
}

@test "fails when pytest execution fails" {
  #R045-T01: Non-zero pytest exit fails the lane with clear output.
  make_venv_python_stub 1 0
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Python unit tests failed"* ]]
}

@test "fails when bats is unavailable" {
  #R001: Script runs in strict mode.
  #R005: Bats is required on PATH.
  #R010: Repo root is resolved from script path.
  #R015: Shell test discovery uses numbered testing/sh lanes.
  #R020: Missing shell tests fail clearly.
  #R025: Bats non-zero fails lane.
  #R030: Success prints single PASS line.
  rm -f "${STUB_BIN}/bats"
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"bats is required"* ]]
}

@test "fails when no shell tests are discovered" {
  make_venv_python_stub 0 0
  rm -f "${FIXTURE_ROOT}/testing/sh/"*.bats
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"No shell unit tests found"* ]]
}

@test "runs pytest then bats and succeeds" {
  #R040-T01: Verify pytest runs against testing/py before Bats shell tests.
  #R015-T02: Verify numbered shell test discovery proceeds after pytest.
  cat > "${FIXTURE_ROOT}/testing/sh/05_run_unit_tests.bats" <<'EOF'
#!/usr/bin/env bats
@test "ok" {
  :
}
EOF
  chmod +x "${FIXTURE_ROOT}/testing/sh/05_run_unit_tests.bats"
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  grep -F "testing/py" "${CALLS_LOG}"
  grep -F "bats " "${CALLS_LOG}"
  [[ "$output" == *"Test Runner: pytest"* ]]
  [[ "$output" == *"Test Runner: Bats"* ]]
  [[ "$output" == *"PASS: Python and shell unit tests completed"* ]]
}
