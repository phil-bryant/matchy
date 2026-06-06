#!/usr/bin/env bash
# Thin pointer: selects the matchy runbook profile and delegates to the runner golden via the shared shim.
RUNBOOK_PROFILE="matchy"
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../runner/src/scripts" && pwd -P)/pointer_shim.sh"
delegate_golden "tests/t04_run_requirements_traceability_tests.sh" "$@"
