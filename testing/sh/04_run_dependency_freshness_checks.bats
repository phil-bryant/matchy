#!/usr/bin/env bats

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "04_run_dependency_freshness_checks.sh"
}

teardown() {
  teardown_shell_test
}

setup_fixture_venv() {
  mkdir -p "${FIXTURE_ROOT}/fixture-venv/bin"
}

stub_pip_outdated_updates() {
  stub_cmd pip "printf 'pip %s\n' \"\$*\" >> '${CALLS_LOG}';
if [ \"\$1\" = list ] && [ \"\$2\" = --outdated ] && [ \"\$3\" = --format=columns ]; then
  cat <<'UPDATES'
Package  Version  Latest  Type
-------- -------  ------  ----
fastapi  0.70.0   1.0.0   wheel
uvicorn  0.15.0   0.30.1  wheel
UPDATES
fi
exit 0"
}

@test "R001,R005,R010,R015,R025: runs from non-root and writes matchy freshness artifacts" {
  #R001-T01: Run from non-root directory verifies reports written under repository-root .security-reports.
  #R005-T01: Run with stubbed pip on PATH verifies selected binary is reported.
  #R010-T01: Run with update-producing stub output verifies text report includes package update entries.
  #R015-T01: Run with update-producing stub output verifies JSON report contains counts and module fields.
  #R025-T01: Run script successfully verifies output includes report paths plus update and major-update counts.
  #R001 #R005 #R010 #R015 #R025
  local script_output
  setup_fixture_venv
  stub_pip_outdated_updates
  run bash -c "cd '${FIXTURE_ROOT}' && \
    export VIRTUAL_ENV=\"\$(cd '${FIXTURE_ROOT}/fixture-venv' && pwd -P)\" && \
    export PATH='${STUB_BIN}:'\${PATH} && \
    ./04_run_dependency_freshness_checks.sh"
  [ "$status" -eq 1 ]
  script_output="$output"
  [[ "$script_output" == *"Python dependency freshness checks"* ]]
  [ -f "${FIXTURE_ROOT}/.security-reports/dependency-freshness.txt" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/dependency-freshness.json" ]
  grep -F "fastapi 0.70.0 -> 1.0.0" "${FIXTURE_ROOT}/.security-reports/dependency-freshness.txt"
  grep -F '"total_updates": 2' "${FIXTURE_ROOT}/.security-reports/dependency-freshness.json"
  grep -F '"major_updates": 1' "${FIXTURE_ROOT}/.security-reports/dependency-freshness.json"
  grep -F '"fail_on_updates": true' "${FIXTURE_ROOT}/.security-reports/dependency-freshness.json"
  [[ "$script_output" == *"json report:"* ]]
}

@test "R005: fails fast when configured pip binary is missing" {
  #R005-T02: Set DEPENDENCY_CHECK_PIP_BIN to missing command verifies non-zero failure.
  #R005
  setup_fixture_venv
  run bash -c "cd '${FIXTURE_ROOT}' && \
    export VIRTUAL_ENV=\"\$(cd '${FIXTURE_ROOT}/fixture-venv' && pwd -P)\" && \
    export PATH='/usr/bin:/bin' && \
    export DEPENDENCY_CHECK_PIP_BIN='pip-does-not-exist' && \
    ./04_run_dependency_freshness_checks.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"pip binary not found on PATH"* ]]
}

@test "R020: fails when major updates exist and fail-on-major is enabled" {
  #R020-T03: Run with major update present and DEPENDENCY_FAIL_ON_MAJOR=true verifies non-zero exit.
  #R020
  setup_fixture_venv
  stub_pip_outdated_updates
  run bash -c "cd '${FIXTURE_ROOT}' && \
    export VIRTUAL_ENV=\"\$(cd '${FIXTURE_ROOT}/fixture-venv' && pwd -P)\" && \
    export PATH='${STUB_BIN}:'\${PATH} && \
    DEPENDENCY_FAIL_ON_MAJOR=true ./04_run_dependency_freshness_checks.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Major dependency updates detected"* ]]
  grep -F '"major_updates": 1' "${FIXTURE_ROOT}/.security-reports/dependency-freshness.json"
}

@test "R020: fails by default when any updates are available" {
  #R020-T01: Run with updates present and default configuration verifies non-zero exit.
  #R020
  setup_fixture_venv
  stub_pip_outdated_updates
  run bash -c "cd '${FIXTURE_ROOT}' && \
    export VIRTUAL_ENV=\"\$(cd '${FIXTURE_ROOT}/fixture-venv' && pwd -P)\" && \
    export PATH='${STUB_BIN}:'\${PATH} && \
    ./04_run_dependency_freshness_checks.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Dependency updates detected"* ]]
}

@test "R020: allows updates when fail-on-updates is disabled" {
  #R020-T02: Run with updates present and DEPENDENCY_FAIL_ON_UPDATES=false verifies zero exit.
  #R020
  setup_fixture_venv
  stub_pip_outdated_updates
  run bash -c "cd '${FIXTURE_ROOT}' && \
    export VIRTUAL_ENV=\"\$(cd '${FIXTURE_ROOT}/fixture-venv' && pwd -P)\" && \
    export PATH='${STUB_BIN}:'\${PATH} && \
    DEPENDENCY_FAIL_ON_UPDATES=false DEPENDENCY_FAIL_ON_MAJOR=false ./04_run_dependency_freshness_checks.sh"
  [ "$status" -eq 0 ]
}
