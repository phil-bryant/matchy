#!/usr/bin/env bash
# Thin runbook pointer: sets RUNBOOK_REPO_ROOT + matchy profile, execs the runner golden.
#R001: Enable secure umask and strict shell mode before delegation.
umask 007
set -euo pipefail
#R005: Resolve script and runner locations from the wrapper path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_HOME="$(cd "${SCRIPT_DIR}/../runner" && pwd)"
#R010: Export repo root context and load matchy runbook profile.
export RUNBOOK_REPO_ROOT="$SCRIPT_DIR"
# shellcheck source=/dev/null
source "${RUNNER_HOME}/config/runbook/matchy.env"
#R015: Delegate to the mapped runner golden with argument passthrough.
exec "${RUNNER_HOME}/11_run_all_tests_parallel.sh" "$@"
