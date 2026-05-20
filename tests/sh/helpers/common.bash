#!/usr/bin/env bash

repo_root() {
  cd "${BATS_TEST_DIRNAME}/../.." && pwd
}

# Copy script(s) once per bats file (setup_file) into BATS_FILE_TMPDIR/shared-source.
setup_file_shared_fixture() {
  : "${BATS_FILE_TMPDIR:?BATS_FILE_TMPDIR is unset; bats >=1.7 required}"
  export SHARED_SOURCE_DIR="${BATS_FILE_TMPDIR}/shared-source"
  mkdir -p "$SHARED_SOURCE_DIR"
  local script_name=""
  for script_name in "$@"; do
    cp "$(repo_root)/${script_name}" "${SHARED_SOURCE_DIR}/${script_name}"
    chmod 770 "${SHARED_SOURCE_DIR}/${script_name}"
  done
}

_resolve_source_path() {
  local rel="$1"
  if [[ -n "${SHARED_SOURCE_DIR:-}" && -e "${SHARED_SOURCE_DIR}/${rel}" ]]; then
    printf '%s' "${SHARED_SOURCE_DIR}/${rel}"
  else
    printf '%s' "$(repo_root)/${rel}"
  fi
}

setup_shell_test() {
  export TEST_TMPDIR
  TEST_TMPDIR="$(mktemp -d)"
  export STUB_BIN="${TEST_TMPDIR}/bin"
  export FIXTURE_ROOT="${TEST_TMPDIR}/fixture"
  export CALLS_LOG="${TEST_TMPDIR}/calls.log"
  mkdir -p "${STUB_BIN}" "${FIXTURE_ROOT}"
  chmod 770 "${STUB_BIN}" "${FIXTURE_ROOT}"
  : > "${CALLS_LOG}"
  chmod 660 "${CALLS_LOG}"
  export PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin"
}

teardown_shell_test() {
  if [[ -n "${TEST_TMPDIR:-}" && -d "${TEST_TMPDIR}" ]]; then
    mv "${TEST_TMPDIR}" "${TEST_TMPDIR}.trash.$$"
  fi
}

create_repo_fixture() {
  mkdir -p "${FIXTURE_ROOT}"
  chmod 770 "${FIXTURE_ROOT}"
}

copy_script_to_fixture() {
  local script_name="$1"
  local src=""
  src="$(_resolve_source_path "${script_name}")"
  cp "${src}" "${FIXTURE_ROOT}/${script_name}"
  chmod 770 "${FIXTURE_ROOT}/${script_name}"
}

stub_cmd() {
  local name="$1"
  local body="$2"
  cat > "${STUB_BIN}/${name}" <<EOF
#!/usr/bin/env bash
${body}
EOF
  chmod 770 "${STUB_BIN}/${name}"
}

run_fixture_script() {
  local script_path="$1"
  shift
  run env PATH="${STUB_BIN}:${PATH}" "$@" bash "${script_path}"
}
