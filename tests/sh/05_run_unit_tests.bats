#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R015-T02 #R020-T01 #R025-T01 #R030-T01 #R035-T01 #R035-T02 #R040-T01 #R045-T01 #R050-T01 #R050-T02 #R050-T03 #R050-T04 #R050-T05 #R050-T06 #R050-T07 #R050-T08 #R050-T09 #R050-T10 #R050-T11

load "helpers/common.bash"

make_venv_python_stub() {
  local pytest_exit_code="${1:-0}"
  local bats_exit_code="${2:-0}"
  mkdir -p "${FIXTURE_ROOT}/matchy-venv/bin" "${FIXTURE_ROOT}/tests/py" "${FIXTURE_ROOT}/tests/sh"
  cat > "${FIXTURE_ROOT}/tests/py/sample_test.py" <<'EOF'
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

write_bats_fixtures() {
  cat > "${FIXTURE_ROOT}/tests/sh/05_example.bats" <<'EOF'
#!/usr/bin/env bats
@test "fixture stub" {
  [ 1 -eq 1 ]
}
EOF
  cat > "${FIXTURE_ROOT}/tests/sh/99_extra.bats" <<'EOF'
#!/usr/bin/env bats
@test "fixture stub 2" {
  [ 1 -eq 1 ]
}
EOF
}

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "05_run_unit_tests.sh"
  make_venv_python_stub 0 0
  write_bats_fixtures
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
  #R005-T01: Bats is required on PATH.
  rm -f "${STUB_BIN}/bats"
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"bats is required"* ]]
}

@test "fails when no shell tests are discovered" {
  #R015-T01: Empty discovered set fails clearly.
  rm -f "${FIXTURE_ROOT}/tests/sh/"*.bats
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"No shell unit tests found"* ]]
}

@test "fails when tests/sh directory is missing" {
  #R020-T01: Missing tests/sh directory fails fast.
  rm -rf "${FIXTURE_ROOT}/tests/sh"
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Bats test directory not found"* ]]
}

@test "runs pytest then parallel bats and succeeds" {
  #R040-T01: Verify pytest runs against tests/py before Bats shell tests.
  #R015-T02: Verify numbered shell test discovery proceeds after pytest.
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  grep -F "tests/py" "${CALLS_LOG}"
  grep -F "bats " "${CALLS_LOG}"
  [[ "$output" == *"Test Runner: pytest"* ]]
  [[ "$output" == *"Test Runner: Bats"* ]]
  [[ "$output" == *"PASS: Python and shell unit tests completed"* ]]
}

@test "invokes bats per file with TAP, failure-output, and timing flags" {
  #R050-T01: Verify parallel bats invocation forwards --tap, --print-output-on-failure, and --timing per file.
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  grep -F -- "--tap" "${CALLS_LOG}"
  grep -F -- "--print-output-on-failure" "${CALLS_LOG}"
  grep -F -- "--timing" "${CALLS_LOG}"
  [ "$(grep -c "bats " "${CALLS_LOG}")" -ge 2 ]
  grep -F "05_example.bats" "${CALLS_LOG}"
  grep -F "99_extra.bats" "${CALLS_LOG}"
}

@test "honors BATS_JOBS env override in progress banner" {
  #R050-T04: BATS_JOBS=1 verifies the resolved-jobs value flows through to the progress banner.
  run env BATS_JOBS=1 bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"jobs=1"* ]]
}

@test "PARALLEL_LANES>1 reduces default bats jobs to keep concurrency near hw.ncpu" {
  #R050-T05: PARALLEL_LANES=99 with BATS_JOBS unset clamps the default to 1.
  run env -u BATS_JOBS PARALLEL_LANES=99 bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"jobs=1"* ]]
}

@test "BATS_FILTER env propagates -f to each bats invocation" {
  #R050-T06: BATS_FILTER=foo verifies -f foo is forwarded to every bats call.
  run env BATS_FILTER=foo bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  grep -F -- "-f foo" "${CALLS_LOG}"
}

@test "BATS_FILTER_STATUS env propagates --filter-status to each bats invocation" {
  #R050-T07: BATS_FILTER_STATUS=failed verifies --filter-status failed is forwarded.
  run env BATS_FILTER_STATUS=failed bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  grep -F -- "--filter-status failed" "${CALLS_LOG}"
}

@test "wraps each bats file output with a basename banner" {
  #R050-T08: Verify the per-file output dump is prefixed by "===== <basename> =====".
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"===== 05_example.bats ====="* ]]
  [[ "$output" == *"===== 99_extra.bats ====="* ]]
}

@test "non-zero exit from any bats file propagates" {
  #R050-T09: A failing bats stub verifies the meta-runner exits non-zero.
  make_venv_python_stub 0 1
  run bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Shell unit tests failed"* ]]
}

@test "BATS_USE_NATIVE_JOBS=true falls back to xargs when parallel is missing" {
  #R050-T10: BATS_USE_NATIVE_JOBS=true with no parallel on PATH verifies fallback notice.
  run env BATS_USE_NATIVE_JOBS=true bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"falling back to xargs"* ]]
  [[ "$output" == *"parallel by file"* ]]
  grep -F "05_example.bats" "${CALLS_LOG}"
}

@test "BATS_USE_NATIVE_JOBS=true delegates to bats -j when parallel is available" {
  #R050-T11: BATS_USE_NATIVE_JOBS=true with stub parallel verifies bats is invoked once with -j.
  rm -f "${FIXTURE_ROOT}/tests/sh/99_extra.bats"
  cat > "${STUB_BIN}/parallel" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "${STUB_BIN}/parallel"
  run env BATS_USE_NATIVE_JOBS=true bash "${FIXTURE_ROOT}/05_run_unit_tests.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"GNU parallel"* ]]
  grep -F -- "-j " "${CALLS_LOG}"
  grep -F -- "--no-parallelize-within-files" "${CALLS_LOG}"
  [ "$(grep -c "^bats " "${CALLS_LOG}")" -eq 1 ]
}
