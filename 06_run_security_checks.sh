#!/usr/bin/env bash
umask 007
#R001: Run security checks in strict fail-fast mode.
set -euo pipefail

#R001: Anchor execution to repository root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

#R005: Keep report output path configurable with deterministic default.
REPORT_DIR="${SECURITY_REPORT_DIR:-./.security-reports}"
FAIL_ON_FINDINGS="${SECURITY_FAIL_ON_FINDINGS:-true}"
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

#R030: Evaluate lane reports and exit codes, print per-lane pass/fail, and gate overall status.
#R050: Honor SECURITY_FAIL_ON_FINDINGS when aggregating lane pass/fail.
emit_lane_results_and_gate() {
  python3 - <<'PY' "$REPORT_DIR" "$FAIL_ON_FINDINGS"
import json
import sys
from pathlib import Path

report_dir = Path(sys.argv[1])
fail_on_findings = sys.argv[2].lower() == "true"
lane_exits_path = report_dir / "lane-exits.env"
lane_exits = {}
if lane_exits_path.exists():
    for line in lane_exits_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            lane_exits[key] = int(value)

def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

def count_shellcheck(payload) -> int:
    return len(payload) if isinstance(payload, list) else 0

def count_semgrep(payload) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return len(payload["results"])
    return 0

def count_gitleaks(payload) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        findings = payload.get("findings")
        if isinstance(findings, list):
            return len(findings)
    return 0

def count_detect_secrets(payload) -> int:
    if not isinstance(payload, dict):
        return 0
    results = payload.get("results")
    if not isinstance(results, dict):
        return 0
    total = 0
    for file_findings in results.values():
        if isinstance(file_findings, list):
            total += len(file_findings)
    return total

def count_ruff(payload) -> int:
    return len(payload) if isinstance(payload, list) else 0

def count_bandit(payload) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return len(payload["results"])
    return 0

def count_pip_audit(payload) -> int:
    dependencies = []
    if isinstance(payload, list):
        dependencies = payload
    if isinstance(payload, dict) and isinstance(payload.get("dependencies"), list):
        dependencies = payload["dependencies"]
    vuln_count = 0
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        vulns = dependency.get("vulns")
        if isinstance(vulns, list) and len(vulns) > 0:
            vuln_count += len(vulns)
    return vuln_count

COUNTERS = {
    "shellcheck": count_shellcheck,
    "semgrep": count_semgrep,
    "gitleaks": count_gitleaks,
    "detect-secrets": count_detect_secrets,
    "ruff": count_ruff,
    "bandit": count_bandit,
    "pip-audit": count_pip_audit,
}

LANES = [
    ("ShellCheck", "shellcheck", "shellcheck.json"),
    ("Semgrep", "semgrep", "semgrep.json"),
    ("Gitleaks", "gitleaks", "gitleaks.json"),
    ("detect-secrets", "detect-secrets", "detect-secrets.json"),
    ("Ruff", "ruff", "ruff.json"),
    ("Bandit", "bandit", "bandit.json"),
    ("pip-audit", "pip-audit", "pip-audit.json"),
]

def lane_failed(tool_key: str, exit_code: int, findings: int, report_valid: bool) -> tuple[bool, str]:
    if exit_code > 1 and tool_key in {"shellcheck", "semgrep", "gitleaks"}:
        return True, f"execution error (exit {exit_code})"
    if not report_valid:
        return True, "report missing or invalid JSON"
    if fail_on_findings and findings > 0:
        return True, f"{findings} finding(s)"
    if exit_code == 1 and tool_key in {"shellcheck", "semgrep", "gitleaks", "ruff", "bandit", "pip-audit"}:
        return True, f"non-zero exit ({exit_code})"
    if exit_code != 0 and tool_key == "detect-secrets":
        return True, f"non-zero exit ({exit_code})"
    return False, "clean"

lane_rows = []
any_failed = False
for display_name, tool_key, report_name in LANES:
    exit_code = lane_exits.get(tool_key, 0)
    payload = load_json(report_dir / report_name)
    report_valid = payload is not None
    findings = COUNTERS[tool_key](payload) if report_valid else 0
    failed, reason = lane_failed(tool_key, exit_code, findings, report_valid)
    if failed:
        any_failed = True
        print(f"❌ FAIL: {display_name} ({reason})")
    else:
        print(f"✅ PASS: {display_name}")
    lane_rows.append(
        {
            "tool": display_name,
            "exit_code": exit_code,
            "findings": findings,
            "passed": not failed,
            "reason": reason,
        }
    )

summary = {
    "lanes": lane_rows,
    "total_findings": sum(row["findings"] for row in lane_rows),
    "gate_failed": any_failed,
    "fail_on_findings": fail_on_findings,
}
summary_path = report_dir / "security-summary.json"
summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print("")
if any_failed:
    print(f"❌ Security checks FAILED. Reports: {report_dir}")
    raise SystemExit(1)
print(f"✅ Security checks PASSED. Reports: {report_dir}")
PY
}

record_lane_exit() {
  printf '%s=%s\n' "$1" "$2" >> "${REPORT_DIR}/lane-exits.env"
}

#R015: Run ShellCheck lane and persist JSON report.
#R055: Print human-readable ShellCheck findings from JSON after the lane completes.
run_shellcheck_lane() {
  local shellcheck_report_path="$1"
  local shellcheck_exit=0
  local shell_targets=()
  shopt -s nullglob
  shell_targets=( ./*.sh ./tests/*.bats ./tests/sh/*.bats )
  shopt -u nullglob
  if [ "${#shell_targets[@]}" -eq 0 ]; then
    shell_targets=( ./06_run_security_checks.sh )
  fi
  print_tool_header \
    "ShellCheck" \
    "Static linting for shell scripts with security and reliability checks." \
    "Flags risky shell patterns, quoting bugs, and execution pitfalls." \
    "https://www.shellcheck.net/"
  echo "Report: ${shellcheck_report_path}"
  echo "▶ Running ShellCheck"
  set +e
  shellcheck -f json "${shell_targets[@]}" > "$shellcheck_report_path"
  shellcheck_exit=$?
  set -e
  record_lane_exit shellcheck "$shellcheck_exit"
  python3 - <<'PY' "$shellcheck_report_path"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else []
if not isinstance(payload, list):
    payload = []
if len(payload) == 0:
    raise SystemExit(0)
print("⚠️  ShellCheck reported findings.")
print("ShellCheck findings")
for finding in payload:
    file_path = str(finding.get("file", "unknown"))
    line = int(finding.get("line", 0))
    code = str(finding.get("code", "unknown"))
    message = str(finding.get("message", "")).strip()
    level = str(finding.get("level", "warning"))
    print(f"- [{level}] {file_path}:{line} SC{code} {message}")
PY
}

#R020: Run Semgrep lane and persist JSON report.
#R055: Print human-readable Semgrep findings from JSON after the lane completes.
run_semgrep_lane() {
  local semgrep_report_path="$1"
  local semgrep_exit=0
  print_tool_header \
    "Semgrep" \
    "Static pattern-based scanning for security and correctness issues." \
    "Uses curated security rules against the repository source tree." \
    "https://semgrep.dev/docs/"
  echo "Report: ${semgrep_report_path}"
  echo "▶ Running Semgrep"
  set +e
  semgrep scan --config auto --json --output "$semgrep_report_path" .
  semgrep_exit=$?
  set -e
  record_lane_exit semgrep "$semgrep_exit"
  python3 - <<'PY' "$semgrep_report_path"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
results = payload.get("results") if isinstance(payload, dict) else []
if not isinstance(results, list):
    results = []
if len(results) == 0:
    raise SystemExit(0)
print("⚠️  Semgrep reported findings.")
print("Semgrep findings")
for finding in results:
    if not isinstance(finding, dict):
        continue
    path = str(finding.get("path", "unknown"))
    start = finding.get("start") if isinstance(finding.get("start"), dict) else {}
    line = int(start.get("line", 0))
    check_id = str(finding.get("check_id", "unknown"))
    extra = finding.get("extra") if isinstance(finding.get("extra"), dict) else {}
    severity = str(extra.get("severity", "unknown"))
    message = str(extra.get("message", "")).strip()
    print(f"- [{severity}] {path}:{line} {check_id}: {message}")
PY
}

#R025: Run Gitleaks lane and persist JSON report.
run_gitleaks_lane() {
  local gitleaks_report_path="$1"
  local gitleaks_exit=0
  print_tool_header \
    "Gitleaks" \
    "Scans repository content for hard-coded secrets and credentials." \
    "Detects leaked tokens, keys, and other sensitive data patterns." \
    "https://github.com/gitleaks/gitleaks"
  echo "Report: ${gitleaks_report_path}"
  echo "▶ Running Gitleaks"
  set +e
  gitleaks detect --source . --no-banner --report-format json --report-path "$gitleaks_report_path"
  gitleaks_exit=$?
  set -e
  record_lane_exit gitleaks "$gitleaks_exit"
  python3 - <<'PY' "$gitleaks_report_path"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else []
findings = payload
if isinstance(payload, dict) and isinstance(payload.get("findings"), list):
    findings = payload["findings"]
if not isinstance(findings, list) or len(findings) == 0:
    raise SystemExit(0)
print("⚠️  Gitleaks reported findings.")
PY
}

#R060: Run detect-secrets with artifact-dir excludes, heartbeat status, and JSON report.
#R055: Print human-readable detect-secrets findings with source lines after the lane completes.
run_detect_secrets_lane() {
  local detect_secrets_report_path="$1"
  local detect_secrets_exit=0
  local detect_secrets_pid=""
  local detect_secrets_elapsed=0
  local detect_secrets_interval=15
  local detect_secrets_exclude_files
  detect_secrets_exclude_files='(^|/)(\.git|\.security-reports|\.cursor|\.pytest_cache|\.ruff_cache|__pycache__|matchy-venv|\.venv|build|dist)(/|$)'
  print_tool_header \
    "detect-secrets" \
    "Scans repository files for high-entropy and known secret formats." \
    "Helps catch accidentally committed credentials before release." \
    "https://github.com/Yelp/detect-secrets"
  echo "Report: ${detect_secrets_report_path}"
  echo "▶ Running detect-secrets"
  echo "  (scan can take several minutes; intermediate status every 15s — JSON written only when complete)"
  detect_secrets_process_alive() {
    local pid="$1"
    local alive=false
    if [[ -n "$pid" ]] && ps -p "$pid" -o pid= | grep -q .; then
      alive=true
    fi
    if [ "$alive" = true ]; then
      return 0
    fi
    return 1
  }
  cleanup_detect_secrets_lane() {
    if detect_secrets_process_alive "$detect_secrets_pid"; then
      kill "$detect_secrets_pid" || true
      wait "$detect_secrets_pid" || true
    fi
  }
  trap cleanup_detect_secrets_lane EXIT INT TERM
  set +e
  detect-secrets scan --all-files --exclude-files "$detect_secrets_exclude_files" > "$detect_secrets_report_path" &
  detect_secrets_pid=$!
  while detect_secrets_process_alive "$detect_secrets_pid"; do
    sleep "$detect_secrets_interval"
    if detect_secrets_process_alive "$detect_secrets_pid"; then
      detect_secrets_elapsed=$((detect_secrets_elapsed + detect_secrets_interval))
      echo "… detect-secrets still running (${detect_secrets_elapsed}s elapsed)"
    fi
  done
  wait "$detect_secrets_pid"
  detect_secrets_exit=$?
  detect_secrets_pid=""
  set -e
  trap - EXIT INT TERM
  record_lane_exit detect-secrets "$detect_secrets_exit"
  python3 - <<'PY' "$detect_secrets_report_path"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
results = payload.get("results") if isinstance(payload, dict) else {}
entries = []
if isinstance(results, dict):
    for file_path, file_findings in results.items():
        if isinstance(file_findings, list):
            for finding in file_findings:
                if isinstance(finding, dict):
                    line_number = int(finding.get("line_number", 0))
                    secret_type = str(finding.get("type", "unknown"))
                    entries.append((str(file_path), line_number, secret_type))
entries.sort(key=lambda item: (item[0], item[1], item[2]))
if len(entries) == 0:
    raise SystemExit(0)
print("⚠️  detect-secrets reported findings.")
print("detect-secrets findings")
for file_path, line_number, secret_type in entries:
    print(f"- {file_path}:{line_number} [{secret_type}]")
    resolved_path = Path(file_path)
    if not resolved_path.is_absolute():
        resolved_path = Path.cwd() / resolved_path
    source_line = "<unavailable>"
    if line_number > 0 and resolved_path.exists():
        file_lines = resolved_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line_number <= len(file_lines):
            source_line = file_lines[line_number - 1]
    print(f"  source: {source_line}")
PY
}

#R020: Run Ruff lane and persist JSON report.
#R055: Print human-readable Ruff findings from JSON after the lane completes.
run_ruff_lane() {
  local ruff_report_path="$1"
  local ruff_exit=0
  print_tool_header \
    "Ruff" \
    "Fast Python linting for style, correctness, and best-practice checks." \
    "Flags Python code issues with modern static analysis rules." \
    "https://docs.astral.sh/ruff/"
  echo "Report: ${ruff_report_path}"
  echo "▶ Running Ruff"
  set +e
  ruff check --output-format json . > "$ruff_report_path"
  ruff_exit=$?
  set -e
  record_lane_exit ruff "$ruff_exit"
  python3 - <<'PY' "$ruff_report_path"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else []
if not isinstance(payload, list):
    payload = []
if len(payload) == 0:
    raise SystemExit(0)
print("⚠️  Ruff reported findings.")
print("Ruff findings")
for finding in payload:
    if not isinstance(finding, dict):
        continue
    filename = str(finding.get("filename", "unknown"))
    location = finding.get("location") if isinstance(finding.get("location"), dict) else {}
    row = int(location.get("row", 0))
    column = int(location.get("column", 0))
    code = str(finding.get("code", "unknown"))
    message = str(finding.get("message", "")).strip()
    severity = str(finding.get("severity", "unknown"))
    print(f"- [{severity}] {filename}:{row}:{column} {code} {message}")
PY
}

#R025: Run Bandit lane and persist JSON report.
#R055: Print human-readable Bandit findings from JSON after the lane completes.
run_bandit_lane() {
  local bandit_report_path="$1"
  local bandit_exit=0
  local python_targets=( ./matchy )
  shopt -s nullglob
  local root_python_scripts=( ./*.py )
  shopt -u nullglob
  if [ "${#root_python_scripts[@]}" -gt 0 ]; then
    python_targets+=( "${root_python_scripts[@]}" )
  fi
  print_tool_header \
    "Bandit" \
    "Python security scanner for common vulnerable coding patterns." \
    "Identifies security smells in Python source and scripts." \
    "https://bandit.readthedocs.io/"
  echo "Report: ${bandit_report_path}"
  echo "▶ Running Bandit"
  set +e
  bandit -ll -r "${python_targets[@]}" -x "./matchy-venv,./.venv,./build,./dist" -f json -o "$bandit_report_path"
  bandit_exit=$?
  set -e
  record_lane_exit bandit "$bandit_exit"
  python3 - <<'PY' "$bandit_report_path"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
results = payload.get("results") if isinstance(payload, dict) else []
if not isinstance(results, list):
    results = []
if len(results) == 0:
    raise SystemExit(0)
print("⚠️  Bandit reported findings.")
print("Bandit findings")
for finding in results:
    if not isinstance(finding, dict):
        continue
    filename = str(finding.get("filename", "unknown"))
    line_number = int(finding.get("line_number", 0))
    test_id = str(finding.get("test_id", "unknown"))
    test_name = str(finding.get("test_name", "")).strip()
    severity = str(finding.get("issue_severity", "unknown"))
    issue_text = str(finding.get("issue_text", "")).strip()
    detail = f"{test_name}: {issue_text}" if test_name else issue_text
    print(f"- [{severity}] {filename}:{line_number} {test_id} {detail}")
PY
}

#R045: Run pip-audit with isolated cache and persist JSON report.
run_pip_audit_lane() {
  local pip_audit_report_path="$1"
  local pip_audit_exit=0
  print_tool_header \
    "pip-audit" \
    "Audits Python dependencies for known vulnerabilities." \
    "Checks installed/project requirements against vulnerability advisories." \
    "https://pypi.org/project/pip-audit/"
  echo "Report: ${pip_audit_report_path}"
  echo "▶ Running pip-audit"
  PIP_CACHE_DIR="${REPORT_DIR}/.pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  export PIP_CACHE_DIR
  set +e
  if [ -f "./requirements.txt" ]; then
    pip-audit -r "./requirements.txt" --format json --output "$pip_audit_report_path"
  else
    pip-audit --format json --output "$pip_audit_report_path"
  fi
  pip_audit_exit=$?
  set -e
  record_lane_exit pip-audit "$pip_audit_exit"
  python3 - <<'PY' "$pip_audit_report_path"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
dependencies = payload if isinstance(payload, list) else payload.get("dependencies", [])
if not isinstance(dependencies, list):
    dependencies = []
vuln_count = 0
for dependency in dependencies:
    if not isinstance(dependency, dict):
        continue
    vulns = dependency.get("vulns")
    if isinstance(vulns, list):
        vuln_count += len(vulns)
if vuln_count == 0:
    raise SystemExit(0)
print(f"⚠️  pip-audit reported {vuln_count} vulnerabilit{'y' if vuln_count == 1 else 'ies'}.")
PY
}

#R010: Validate required commands before running lanes.
require_command shellcheck
require_command semgrep
require_command gitleaks
require_command detect-secrets
require_command ruff
require_command bandit
require_command pip-audit

: > "${REPORT_DIR}/lane-exits.env"

run_shellcheck_lane "${REPORT_DIR}/shellcheck.json"
run_semgrep_lane "${REPORT_DIR}/semgrep.json"
run_gitleaks_lane "${REPORT_DIR}/gitleaks.json"
run_detect_secrets_lane "${REPORT_DIR}/detect-secrets.json"
run_ruff_lane "${REPORT_DIR}/ruff.json"
run_bandit_lane "${REPORT_DIR}/bandit.json"
run_pip_audit_lane "${REPORT_DIR}/pip-audit.json"

emit_lane_results_and_gate
