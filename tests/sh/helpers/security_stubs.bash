#!/usr/bin/env bash
# Shared stubs for 06_run_security_checks_*.bats (valve-style). Loaded after helpers/common.bash.

_security_stub_escape() {
  local raw="$1"
  raw="${raw//\\/\\\\}"
  raw="${raw//\"/\\\"}"
  printf '%s' "$raw"
}

make_shellcheck_stub() {
  local payload="${1:-[]}"
  local body="$(_security_stub_escape "$payload")"
  cat > "${STUB_BIN}/shellcheck" <<EOF
#!/usr/bin/env bash
printf '%s' "${body}"
exit 0
EOF
  chmod 770 "${STUB_BIN}/shellcheck"
}

make_semgrep_stub() {
  cat > "${STUB_BIN}/semgrep" <<'EOF'
#!/usr/bin/env bash
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output" ]; then
    out="$2"
    shift 2
    continue
  fi
  shift
done
printf '%s' '{"results":[]}' > "$out"
exit 0
EOF
  chmod 770 "${STUB_BIN}/semgrep"
}

make_gitleaks_stub() {
  local payload="${1:-[]}"
  local body="$(_security_stub_escape "$payload")"
  cat > "${STUB_BIN}/gitleaks" <<EOF
#!/usr/bin/env bash
while [ "\$#" -gt 0 ]; do
  if [ "\$1" = "--report-path" ]; then
    printf '%s' "${body}" > "\$2"
    exit 0
  fi
  shift
done
exit 0
EOF
  chmod 770 "${STUB_BIN}/gitleaks"
}

make_detect_secrets_stub() {
  local payload='{"results":{}}'
  if [ "$#" -gt 0 ]; then payload="$1"; fi
  local body="$(_security_stub_escape "$payload")"
  local extra="${2:-}"
  cat > "${STUB_BIN}/detect-secrets" <<EOF
#!/usr/bin/env bash
${extra}
printf '%s' "${body}"
exit 0
EOF
  chmod 770 "${STUB_BIN}/detect-secrets"
}

make_ruff_stub() {
  local payload="${1:-[]}"
  local body="$(_security_stub_escape "$payload")"
  cat > "${STUB_BIN}/ruff" <<EOF
#!/usr/bin/env bash
printf '%s' "${body}"
exit 0
EOF
  chmod 770 "${STUB_BIN}/ruff"
}

make_bandit_stub() {
  local payload='{"results":[]}'
  if [ "$#" -gt 0 ]; then payload="$1"; fi
  local body="$(_security_stub_escape "$payload")"
  cat > "${STUB_BIN}/bandit" <<EOF
#!/usr/bin/env bash
while [ "\$#" -gt 0 ]; do
  if [ "\$1" = "-o" ]; then
    printf '%s' "${body}" > "\$2"
    exit 0
  fi
  shift
done
exit 0
EOF
  chmod 770 "${STUB_BIN}/bandit"
}

make_pip_audit_stub() {
  local payload='{"dependencies":[]}'
  if [ "$#" -gt 0 ]; then payload="$1"; fi
  local body="$(_security_stub_escape "$payload")"
  local extra="${2:-}"
  cat > "${STUB_BIN}/pip-audit" <<EOF
#!/usr/bin/env bash
${extra}
while [ "\$#" -gt 0 ]; do
  if [ "\$1" = "--output" ]; then
    printf '%s' "${body}" > "\$2"
    exit 0
  fi
  shift
done
exit 0
EOF
  chmod 770 "${STUB_BIN}/pip-audit"
}

stub_security_tools_pass() {
  make_shellcheck_stub '[]'
  make_semgrep_stub
  make_gitleaks_stub '[]'
  make_detect_secrets_stub '{"results":{}}'
  make_ruff_stub '[]'
  make_bandit_stub '{"results":[]}'
  make_pip_audit_stub '{"dependencies":[]}'
}

setup_security_fixture() {
  create_repo_fixture
  copy_script_to_fixture "06_run_security_checks.sh"
}

setup_security_test() {
  setup_shell_test
  setup_security_fixture
}

run_security_script() {
  local lanes="$1"
  shift
  run_fixture_script "${FIXTURE_ROOT}/06_run_security_checks.sh" \
    SECURITY_RUN_LANES="${lanes}" \
    DETECT_SECRETS_USE_BACKGROUND_WAIT=false \
    "$@"
}
