#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R020-T01 #R025-T01 #R030-T01 #R030-T02 #R035-T01 #R040-T01 #R045-T01 #R045-T02 #R050-T01 #R065-T01

load "helpers/common.bash"
load "helpers/security_stubs.bash"

setup_file() {
  setup_file_shared_fixture "06_run_security_checks.sh"
}

setup() {
  setup_security_test
}

teardown() {
  teardown_shell_test
}

@test "fails when shellcheck is missing" {
  #R001 #R005 #R010 #R015 #R020 #R025 #R030 #R035 #R040
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Missing required command: shellcheck"* ]]
}

@test "writes report files when tools are available" {
  #R015 #R025 #R030 #R035 #R040
  stub_security_tools_pass
  cat > "${STUB_BIN}/bandit" <<EOF
#!/usr/bin/env bash
printf '%s' "\$*" > "${FIXTURE_ROOT}/bandit-args.txt"
while [ "\$#" -gt 0 ]; do
  if [ "\$1" = "-o" ]; then printf '%s' '{"results":[]}' > "\$2"; exit 0; fi
  shift
done
exit 0
EOF
  chmod 770 "${STUB_BIN}/bandit"
  cat > "${STUB_BIN}/pip-audit" <<EOF
#!/usr/bin/env bash
printf '%s' "\$*" > "${FIXTURE_ROOT}/pip-audit-args.txt"
while [ "\$#" -gt 0 ]; do
  if [ "\$1" = "--output" ]; then printf '%s' '{"dependencies":[]}' > "\$2"; exit 0; fi
  shift
done
exit 0
EOF
  chmod 770 "${STUB_BIN}/pip-audit"
  cat > "${FIXTURE_ROOT}/requirements.txt" <<'EOF'
requests>=2.34.0
EOF
  run_security_script "shellcheck,bandit,pip-audit"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Security Tool: ShellCheck"* ]]
  [[ "$output" == *"✅ Security checks PASSED. Reports:"* ]]
  [ -f "${FIXTURE_ROOT}/.security-reports/shellcheck.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/pip-audit.json" ]
  bandit_args="$(<"${FIXTURE_ROOT}/bandit-args.txt")"
  [[ "$bandit_args" == *"./matchy"* ]]
  pip_audit_args="$(<"${FIXTURE_ROOT}/pip-audit-args.txt")"
  [[ "$pip_audit_args" == *"requirements.txt"* ]]
}

@test "uses isolated pip-audit cache directory to avoid stale-cache warnings" {
  #R045-T01 #R045-T02 #R065-T01
  cat > "${STUB_BIN}/pip-audit" <<EOF
#!/usr/bin/env bash
printf '%s' "\$PIP_CACHE_DIR" > "${FIXTURE_ROOT}/pip-cache-dir.txt"
while [ "\$#" -gt 0 ]; do
  if [ "\$1" = "--output" ]; then printf '%s' '{"dependencies":[]}' > "\$2"; exit 0; fi
  shift
done
exit 0
EOF
  chmod 770 "${STUB_BIN}/pip-audit"
  cat > "${FIXTURE_ROOT}/requirements.txt" <<'EOF'
requests>=2.34.0
EOF
  run_security_script "pip-audit"
  [ "$status" -eq 0 ]
  [ -d "${FIXTURE_ROOT}/.security-reports/.pip-cache" ]
  pip_cache_dir="$(<"${FIXTURE_ROOT}/pip-cache-dir.txt")"
  [ "$pip_cache_dir" = "./.security-reports/.pip-cache" ]
  [[ "$output" == *"▶ Running pip-audit"* ]]
}

@test "fails when a lane reports findings" {
  #R030 #R050 #R055-T01
  make_shellcheck_stub '[{"file":"bad.sh","line":1,"code":2086,"message":"issue","level":"warning"}]'
  cat > "${STUB_BIN}/shellcheck" <<'EOF'
#!/usr/bin/env bash
printf '%s' '[{"file":"bad.sh","line":1,"code":2086,"message":"issue","level":"warning"}]'
exit 1
EOF
  chmod 770 "${STUB_BIN}/shellcheck"
  make_semgrep_stub
  run_security_script "shellcheck,semgrep"
  [ "$status" -ne 0 ]
  [[ "$output" == *"ShellCheck findings"* ]]
  [[ "$output" == *"✅ PASS: Semgrep"* ]]
  [[ "$output" == *"❌ Security checks FAILED. Reports:"* ]]
}
