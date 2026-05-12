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

# Borrowed header format from ../piston/03_run_security_checks.sh.
#R035: Print standardized manifold-style tool header blocks.
print_tool_header() {
  local tool_name="$1"
  local explainer_line_1="$2"
  local explainer_line_2="$3"
  local tool_url="$4"
  local border="+==============================================================================+"
  printf '%s\n' "$border"
  printf '| %-76s |\n' "Security Tool: ${tool_name}"
  printf '| %-76s |\n' "${explainer_line_1}"
  printf '| %-76s |\n' "${explainer_line_2}"
  printf '| %-76s |\n' "URL: ${tool_url}"
  printf '%s\n' "$border"
}

#R015: Run ShellCheck lane and persist JSON output.
require_command shellcheck
#R020: Run Semgrep lane and persist JSON output.
require_command semgrep
#R025: Run Gitleaks lane and persist JSON output.
require_command gitleaks
require_command detect-secrets
require_command ruff
require_command bandit
require_command pip-audit

shopt -s nullglob
shell_targets=( ./*.sh ./testing/*.bats ./testing/sh/*.bats )
shopt -u nullglob
if [ "${#shell_targets[@]}" -eq 0 ]; then
  shell_targets=( ./05_run_security_checks.sh )
fi

print_tool_header \
  "ShellCheck" \
  "Static linting for shell scripts with security and reliability checks." \
  "Flags risky shell patterns, quoting bugs, and execution pitfalls." \
  "https://www.shellcheck.net/"
echo "Report: ${REPORT_DIR}/shellcheck.json"
#R040: Print explicit lane running indicators before execution.
echo "▶ Running ShellCheck"
shellcheck -f json "${shell_targets[@]}" > "${REPORT_DIR}/shellcheck.json" || true

print_tool_header \
  "Semgrep" \
  "Static pattern-based scanning for security and correctness issues." \
  "Uses curated security rules against the repository source tree." \
  "https://semgrep.dev/docs/"
echo "Report: ${REPORT_DIR}/semgrep.json"
echo "▶ Running Semgrep"
semgrep scan --config auto --json --output "${REPORT_DIR}/semgrep.json" . || true

print_tool_header \
  "Gitleaks" \
  "Scans repository content for hard-coded secrets and credentials." \
  "Detects leaked tokens, keys, and other sensitive data patterns." \
  "https://github.com/gitleaks/gitleaks"
echo "Report: ${REPORT_DIR}/gitleaks.json"
echo "▶ Running Gitleaks"
gitleaks detect --source . --no-banner --report-format json --report-path "${REPORT_DIR}/gitleaks.json" || true

print_tool_header \
  "detect-secrets" \
  "Scans repository files for high-entropy and known secret formats." \
  "Helps catch accidentally committed credentials before release." \
  "https://github.com/Yelp/detect-secrets"
echo "Report: ${REPORT_DIR}/detect-secrets.json"
echo "▶ Running detect-secrets"
detect-secrets scan --all-files > "${REPORT_DIR}/detect-secrets.json" || true

print_tool_header \
  "Ruff" \
  "Fast Python linting for style, correctness, and best-practice checks." \
  "Flags Python code issues with modern static analysis rules." \
  "https://docs.astral.sh/ruff/"
echo "Report: ${REPORT_DIR}/ruff.json"
echo "▶ Running Ruff"
ruff check --output-format json . > "${REPORT_DIR}/ruff.json" || true

print_tool_header \
  "Bandit" \
  "Python security scanner for common vulnerable coding patterns." \
  "Identifies security smells in Python source and scripts." \
  "https://bandit.readthedocs.io/"
echo "Report: ${REPORT_DIR}/bandit.json"
echo "▶ Running Bandit"
python_targets=( ./matchy )
shopt -s nullglob
root_python_scripts=( ./*.py )
shopt -u nullglob
if [ "${#root_python_scripts[@]}" -gt 0 ]; then
  python_targets+=( "${root_python_scripts[@]}" )
fi
bandit -r "${python_targets[@]}" -x "./matchy-venv,./.venv,./build,./dist" -f json -o "${REPORT_DIR}/bandit.json" || true

print_tool_header \
  "pip-audit" \
  "Audits Python dependencies for known vulnerabilities." \
  "Checks installed/project requirements against vulnerability advisories." \
  "https://pypi.org/project/pip-audit/"
echo "Report: ${REPORT_DIR}/pip-audit.json"
echo "▶ Running pip-audit"
if [ -f "./requirements.txt" ]; then
  pip-audit -r "./requirements.txt" --format json --output "${REPORT_DIR}/pip-audit.json" || true
else
  pip-audit --format json --output "${REPORT_DIR}/pip-audit.json" || true
fi

#R030: Emit deterministic completion line with report path.
echo "✅ Security checks completed. Reports: ${REPORT_DIR}"
