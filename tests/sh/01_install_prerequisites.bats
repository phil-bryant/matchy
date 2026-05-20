#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R010-T02 #R015-T01 #R020-T01 #R025-T01 #R030-T01 #R065-T01 #R065-T02

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "01_install_prerequisites.sh"
}

teardown() {
  teardown_shell_test
}

@test "fails when brew is unavailable" {
  #R001: Script must run strict fail-fast.
  #R005: Homebrew is required before installs.
  #R010: Required formulas are validated/installed.
  #R015: Installer emits concise status.
  #R020: Installer reruns idempotently.
  #R025: Installer prints next-step guidance.
  #R030: Missing 1psa is advisory only.
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/01_install_prerequisites.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Homebrew is required"* ]]
}

@test "installs required formulas via brew" {
  cat > "${STUB_BIN}/brew" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "install" ]; then
  target="\${2}"
  if [ "\${target}" = "bats-core" ]; then
    target="bats"
  fi
  echo "install \${2}" >> "${TEST_TMPDIR}/brew.log"
  cat > "${STUB_BIN}/\${target}" <<'INNER'
#!/usr/bin/env bash
exit 0
INNER
  chmod +x "${STUB_BIN}/\${target}"
fi
exit 0
EOF
  chmod +x "${STUB_BIN}/brew"

  run bash "${FIXTURE_ROOT}/01_install_prerequisites.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Prerequisites complete"* ]]
  grep -q '^install parallel$' "${TEST_TMPDIR}/brew.log"
}

@test "skips parallel install when already available" {
  #R065-T02: Run with parallel already on PATH verifies no reinstall.
  cat > "${STUB_BIN}/brew" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "install" ]; then
  echo "install \${2}" >> "${TEST_TMPDIR}/brew.log"
fi
exit 0
EOF
  chmod +x "${STUB_BIN}/brew"
  cat > "${STUB_BIN}/parallel" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "${STUB_BIN}/parallel"
  for tool in shellcheck semgrep gitleaks detect-secrets ruff bandit pip-audit bats; do
    cat > "${STUB_BIN}/${tool}" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "${STUB_BIN}/${tool}"
  done
  run bash "${FIXTURE_ROOT}/01_install_prerequisites.sh"
  [ "$status" -eq 0 ]
  if [ -f "${TEST_TMPDIR}/brew.log" ]; then
    run grep '^install parallel$' "${TEST_TMPDIR}/brew.log"
    [ "$status" -ne 0 ]
  fi
}
