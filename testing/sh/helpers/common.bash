#!/usr/bin/env bash

repo_root() {
  cd "${BATS_TEST_DIRNAME}/../.." && pwd
}

setup_shell_test() {
  export TEST_TMPDIR
  TEST_TMPDIR="$(mktemp -d)"
  export STUB_BIN="${TEST_TMPDIR}/bin"
  export FIXTURE_ROOT="${TEST_TMPDIR}/fixture"
  export CALLS_LOG="${TEST_TMPDIR}/calls.log"
  mkdir -p "${STUB_BIN}" "${FIXTURE_ROOT}"
  : > "${CALLS_LOG}"
  export PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin"
}

teardown_shell_test() {
  rm -rf "${TEST_TMPDIR}"
}

create_repo_fixture() {
  mkdir -p "${FIXTURE_ROOT}"
}

copy_script_to_fixture() {
  local script_name="$1"
  cp "$(repo_root)/${script_name}" "${FIXTURE_ROOT}/${script_name}"
  chmod +x "${FIXTURE_ROOT}/${script_name}"
}

stub_cmd() {
  local name="$1"
  local body="$2"
  cat > "${STUB_BIN}/${name}" <<EOF
#!/usr/bin/env bash
${body}
EOF
  chmod +x "${STUB_BIN}/${name}"
}
