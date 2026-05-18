#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R010-T02 #R015-T01 #R020-T01 #R025-T01 #R030-T01

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
}
