#!/usr/bin/env bash
# Thin test pointer: sets RUNBOOK_REPO_ROOT + matchy profile, execs the runner test golden.
umask 007
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_HOME="$(cd "${SCRIPT_DIR}/../../runner" && pwd)"
RUNBOOK_REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export RUNBOOK_REPO_ROOT
# shellcheck source=/dev/null
source "${RUNNER_HOME}/config/runbook/matchy.env"
exec "${RUNNER_HOME}/tests/t11_run_fuzz_tests.sh" "$@"
