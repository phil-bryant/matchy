#!/usr/bin/env bash
umask 007
#R001: Run security checks in strict fail-fast mode.
set -euo pipefail

#R001: Anchor execution to repository root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

#R005: Keep report output path configurable with deterministic default.
REPORT_DIR="${SECURITY_REPORT_DIR:-./.security-reports}"
mkdir -p "$REPORT_DIR"

#R010: Provide explicit missing-command failures for enabled tools.
require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "❌ Missing required command: $1"
    exit 1
  fi
}

#R015: Run ShellCheck lane and persist JSON output.
require_command shellcheck
#R020: Run Semgrep lane and persist JSON output.
require_command semgrep
#R025: Run Gitleaks lane and persist JSON output.
require_command gitleaks

shopt -s nullglob
shell_targets=( ./*.sh ./testing/*.bats ./testing/sh/*.bats )
shopt -u nullglob
if [ "${#shell_targets[@]}" -eq 0 ]; then
  shell_targets=( ./05_run_security_checks.sh )
fi
shellcheck -f json "${shell_targets[@]}" > "${REPORT_DIR}/shellcheck.json" || true
semgrep --config auto --json --output "${REPORT_DIR}/semgrep.json" . || true
gitleaks detect --source . --no-banner --report-format json --report-path "${REPORT_DIR}/gitleaks.json" || true

#R030: Emit deterministic completion line with report path.
echo "✅ Security checks completed. Reports: ${REPORT_DIR}"
