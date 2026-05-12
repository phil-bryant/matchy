#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/.." && pwd)"
  export TMP_ROOT="$(mktemp -d)"
  export SANDBOX="${TMP_ROOT}/sandbox"
  export STUB_BIN="${TMP_ROOT}/bin"
  export LOG_FILE="${TMP_ROOT}/tool.log"
  mkdir -p "${SANDBOX}" "${STUB_BIN}" "${SANDBOX}/testing/sh" "${SANDBOX}/matchy"
  cp "${REPO_ROOT}/Makefile" "${SANDBOX}/Makefile"
  : > "${LOG_FILE}"
}

teardown() {
  rm -rf "${TMP_ROOT}"
}

create_stub() {
  local name="$1" body="$2"
  cat > "${STUB_BIN}/${name}" <<EOF
#!/bin/bash
${body}
EOF
  chmod +x "${STUB_BIN}/${name}"
}

create_common_stubs() {
  create_stub "bats" "echo bats \"\$@\" >> \"${LOG_FILE}\"; exit 0"
  create_stub "shellcheck" "echo shellcheck \"\$@\" >> \"${LOG_FILE}\"; printf '[]'"
  create_stub "semgrep" "echo semgrep \"\$@\" >> \"${LOG_FILE}\"; while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done"
  create_stub "gitleaks" "echo gitleaks \"\$@\" >> \"${LOG_FILE}\"; while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done"
  create_stub "clamscan" "echo 'Scanned files: 1'; echo 'Infected files: 0'; exit 0"
  cat > "${SANDBOX}/testing/sh/example.bats" <<'EOF'
#!/usr/bin/env bats
@test "fixture" { true; }
EOF
  chmod +x "${SANDBOX}/testing/sh/example.bats"
  cat > "${SANDBOX}/pyproject.toml" <<'EOF'
[project]
name = "matchy"
version = "0.0.0"
EOF
  cat > "${SANDBOX}/matchy/api.py" <<'EOF'
def create_app():
    return {}
EOF
  for script in 04_run_unit_tests.sh 05_run_security_checks.sh 06_run_av_checks.sh 07_run_matchy_api.py; do
    cat > "${SANDBOX}/${script}" <<EOF
#!/usr/bin/env bash
echo "${script}" >> "${LOG_FILE}"
exit 0
EOF
    chmod +x "${SANDBOX}/${script}"
  done
}

@test "help lists matchy targets" {
  #R001: Validate help target coverage.
  #R005: Validate build verification workflow.
  #R010: Validate make test routing behavior.
  #R015: Validate make run routing behavior.
  #R020: Validate security/av lane routing behavior.
  #R025: Validate helper alias target contract.
  #R030: Validate clean idempotent artifact handling.
  run env PATH="${STUB_BIN}:/usr/bin:/bin" make -f "${SANDBOX}/Makefile" -C "${SANDBOX}" help
  [ "$status" -eq 0 ]
  [[ "$output" == *"build"* ]]
  [[ "$output" == *"test"* ]]
  [[ "$output" == *"run"* ]]
  [[ "$output" == *"sast"* ]]
  [[ "$output" == *"clean"* ]]
}

@test "build validates required files" {
  create_common_stubs
  run env PATH="${STUB_BIN}:/usr/bin:/bin" make -f "${SANDBOX}/Makefile" -C "${SANDBOX}" build
  [ "$status" -eq 0 ]
}

@test "test target runs unit test script" {
  create_common_stubs
  run env PATH="${STUB_BIN}:/usr/bin:/bin" make -f "${SANDBOX}/Makefile" -C "${SANDBOX}" test
  [ "$status" -eq 0 ]
  run rg "04_run_unit_tests\\.sh" "${LOG_FILE}"
  [ "$status" -eq 0 ]
}

@test "run target launches api script" {
  create_common_stubs
  run env PATH="${STUB_BIN}:/usr/bin:/bin" make -f "${SANDBOX}/Makefile" -C "${SANDBOX}" run
  [ "$status" -eq 0 ]
  run rg "07_run_matchy_api\\.py" "${LOG_FILE}"
  [ "$status" -eq 0 ]
}

@test "sast target runs security script" {
  create_common_stubs
  run env PATH="${STUB_BIN}:/usr/bin:/bin" make -f "${SANDBOX}/Makefile" -C "${SANDBOX}" sast
  [ "$status" -eq 0 ]
  run rg "05_run_security_checks\\.sh" "${LOG_FILE}"
  [ "$status" -eq 0 ]
}

@test "clean removes build artifacts" {
  create_common_stubs
  mkdir -p "${SANDBOX}/build" "${SANDBOX}/.security-reports"
  run env PATH="${STUB_BIN}:/usr/bin:/bin" HOME="${SANDBOX}" make -f "${SANDBOX}/Makefile" -C "${SANDBOX}" clean
  [ "$status" -eq 0 ]
  [ ! -e "${SANDBOX}/build" ]
  [ ! -e "${SANDBOX}/.security-reports" ]
}
