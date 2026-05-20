#!/usr/bin/env bats
#R001-T01 #R005-T01 #R005-T02 #R010-T01 #R015-T01 #R015-T02 #R020-T01 #R020-T02 #R020-T03 #R025-T01 #R030-T01

load "helpers/common.bash"

make_venv_python_stub() {
  local pytest_exit="${1:-0}"
  local hypothesis_ok="${2:-true}"
  local passing_each="${3:-500}"
  local property_test_count="${4:-13}"
  local real_python
  real_python="$(command -v python3)"
  mkdir -p "${FIXTURE_ROOT}/matchy-venv/bin" "${FIXTURE_ROOT}/tests/py" "${FIXTURE_ROOT}/.security-reports"
  cat > "${FIXTURE_ROOT}/tests/py/test_scoring_properties.py" <<'EOF'
def test_property_ok():
    assert True
EOF
  cat > "${FIXTURE_ROOT}/matchy-venv/bin/python" <<EOF
#!/usr/bin/env bash
if [ "\${1:-}" = "-c" ] && [[ "\$*" == *"import hypothesis"* ]]; then
  if [ "${hypothesis_ok}" = "true" ]; then
    exit 0
  fi
  exit 1
fi
if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "pytest" ]; then
  echo "pytest \$*" >> "${CALLS_LOG}"
  echo "HYPOTHESIS_MAX_EXAMPLES=\${HYPOTHESIS_MAX_EXAMPLES:-}" >> "${CALLS_LOG}"
  echo "HYPOTHESIS_DEADLINE=\${HYPOTHESIS_DEADLINE:-}" >> "${CALLS_LOG}"
  index=0
  while [ "\$index" -lt "${property_test_count}" ]; do
    printf 'tests/py/test_scoring_properties.py::test_property_%s:\\n' "\$index"
    printf '    - ${passing_each} passing examples, 0 failing examples, 0 invalid examples\\n'
    index=\$((index + 1))
  done
  if [ ${pytest_exit} -ne 0 ]; then
    echo "1 failed"
  else
    echo "${property_test_count} passed"
  fi
  exit ${pytest_exit}
fi
if [ "\${1:-}" = "-" ] && [[ "\${2:-}" =~ ^[0-9]+\$ ]]; then
  shift 2
  exec "\$@"
fi
if [ "\${1:-}" = "-" ] && [ -f "\${2:-}" ]; then
  shift
  exec "${real_python}" - "\$@"
fi
exit 0
EOF
  chmod +x "${FIXTURE_ROOT}/matchy-venv/bin/python"
  : > "${CALLS_LOG}"
}

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "11_run_fuzz.sh"
  make_venv_python_stub 0 true 500 13
}

teardown() {
  teardown_shell_test
}

@test "runs fuzz tests from non-repo cwd" {
  #R001-T01: Run from non-repo cwd verifies fuzz invocation still targets repository tests.
  mkdir -p "${TEST_TMPDIR}/elsewhere"
  run bash -c "cd '${TEST_TMPDIR}/elsewhere' && bash '${FIXTURE_ROOT}/11_run_fuzz.sh'"
  [ "$status" -eq 0 ]
}

@test "fails when matchy-venv python is unavailable" {
  #R005-T01: Run without venv python verifies non-zero failure.
  rm -rf "${FIXTURE_ROOT}/matchy-venv"
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"matchy-venv python is required"* ]]
}

@test "fails when hypothesis is unavailable" {
  #R005-T02: Run without hypothesis verifies non-zero failure.
  make_venv_python_stub 0 false
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"hypothesis is required"* ]]
}

@test "invokes pytest with default fuzz paths and hypothesis env" {
  #R010-T01: Verify fuzz paths, Hypothesis env vars, and statistics flag appear in invocation log.
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -eq 0 ]
  grep -F "tests/py/test_scoring_properties.py" "${CALLS_LOG}"
  grep -F "HYPOTHESIS_MAX_EXAMPLES=500" "${CALLS_LOG}"
  grep -F "HYPOTHESIS_DEADLINE=1000" "${CALLS_LOG}"
  grep -e "--hypothesis-show-statistics" "${CALLS_LOG}"
  grep -e "-p hypothesis" "${CALLS_LOG}"
}

@test "emits pass output on successful run" {
  #R015-T01: Run successful fuzz stub path and verify pass output line.
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"✅ PASS: Property-based fuzz tests completed"* ]]
}

@test "writes fuzz summary json under report dir" {
  #R015-T02: Verify fuzz summary JSON is written under report dir.
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -eq 0 ]
  [ -f "${FIXTURE_ROOT}/.security-reports/fuzz-summary.json" ]
  grep -F '"gate_failed": false' "${FIXTURE_ROOT}/.security-reports/fuzz-summary.json"
}

@test "fails when example budget is below threshold" {
  #R020-T01: Simulate statistics below the example budget and verify explicit non-zero failure.
  make_venv_python_stub 0 true 10 13
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"below budget"* ]]
}

@test "passes when example budget is met" {
  #R020-T02: Simulate statistics at or above the example budget with pytest success and verify pass.
  make_venv_python_stub 0 true 500 13
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"passing_examples=6500"* ]]
}

@test "fails when pytest returns non-zero" {
  #R020-T03: Simulate pytest failure and verify non-zero failure even when statistics are present.
  make_venv_python_stub 1 true 500 13
  run bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"pytest failures"* ]]
}

@test "fuzz suite includes semantic normalization and time-bucket properties" {
  #R030-T01: Verify property tests assert normalization charset and time buckets.
  run grep -E 'test_normalized_text|test_time_proximity_matches_bucket' "$(repo_root)/tests/py/test_scoring_properties.py"
  [ "$status" -eq 0 ]
}

@test "fails when fuzz lane times out" {
  #R025-T01: Simulate timeout exit code and verify explicit non-zero failure output.
  cat > "${FIXTURE_ROOT}/matchy-venv/bin/python" <<EOF
#!/usr/bin/env bash
if [ "\${1:-}" = "-c" ] && [[ "\$*" == *"import hypothesis"* ]]; then
  exit 0
fi
if [ "\${1:-}" = "-" ] && [[ "\${2:-}" =~ ^[0-9]+\$ ]]; then
  exit 124
fi
exit 0
EOF
  chmod +x "${FIXTURE_ROOT}/matchy-venv/bin/python"
  run env FUZZ_TIMEOUT_SECONDS=1 bash "${FIXTURE_ROOT}/11_run_fuzz.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"timed out"* ]]
}
