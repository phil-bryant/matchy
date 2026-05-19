#!/bin/bash
umask 007
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#R001: Resolve repository root from script location so report and module paths are deterministic.
cd "$SCRIPT_DIR"

# Validate project virtual environment is present and active before running checks.
CURRENT_DIRECTORY_NAME=$(basename "$(pwd)")
VENV_DIR="${CURRENT_DIRECTORY_NAME}-venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "❌ ERROR: Virtual environment not found!"
  echo ""
  echo "Please run the virtual environment setup first:"
  echo "  ./02_create_venv.sh"
  echo ""
  echo "This will create the required virtual environment: $VENV_DIR"
  exit 1
fi
if [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "❌ ERROR: No virtual environment is currently active!"
  echo ""
  echo "Please activate the virtual environment first:"
  echo "  activate"
  echo ""
  echo "Then run this script again."
  exit 1
fi
EXPECTED_VENV_PATH=$(cd "$VENV_DIR" && pwd -P)
CURRENT_VENV_PATH="$VIRTUAL_ENV"
if [ -d "$VIRTUAL_ENV" ]; then
  CURRENT_VENV_PATH=$(cd "$VIRTUAL_ENV" && pwd -P)
fi
if [ "$CURRENT_VENV_PATH" != "$EXPECTED_VENV_PATH" ]; then
  echo "⚠️  WARNING: You are using a different virtual environment!"
  echo "Expected: $EXPECTED_VENV_PATH"
  echo "Current:  $CURRENT_VENV_PATH"
  echo ""
  echo "Please deactivate and reactivate the correct virtual environment:"
  echo "  deactivate"
  echo "  activate"
  exit 1
fi

REPORT_DIR="${DEPENDENCY_REPORT_DIR:-./.security-reports}"
PIP_BIN="${DEPENDENCY_CHECK_PIP_BIN:-pip}"
FAIL_ON_MAJOR="${DEPENDENCY_FAIL_ON_MAJOR:-false}"
FAIL_ON_ANY="${DEPENDENCY_FAIL_ON_UPDATES:-true}"
TEXT_REPORT="${REPORT_DIR}/dependency-freshness.txt"
JSON_REPORT="${REPORT_DIR}/dependency-freshness.json"
UPDATES_FILE="$(mktemp)"
WARNINGS_FILE="$(mktemp)"

major_from_version() {
  local version="$1"
  local normalized major
  normalized="${version#v}"
  major="${normalized%%.*}"
  if [[ -z "$major" ]]; then
    major="0"
  fi
  printf "%s" "$major"
}

#R005: Use configurable pip binary and fail fast when it is unavailable.
if ! command -v "$PIP_BIN" >/dev/null 2>&1; then
  echo "❌ pip binary not found on PATH: ${PIP_BIN}"
  exit 1
fi

mkdir -p "$REPORT_DIR"
echo "▶ Running Python dependency freshness checks with ${PIP_BIN}"

#R010: Discover available dependency updates from pip and always emit a text artifact.
PIP_NO_CACHE_DIR=1 "$PIP_BIN" list --outdated --format=columns 2> "$WARNINGS_FILE" | awk 'NR > 2 && NF >= 3 { print $1, $2, $3 }' > "$UPDATES_FILE"
if [[ -s "$WARNINGS_FILE" ]]; then
  echo "⚠️ pip emitted warnings during dependency check:"
  sed 's/^/   /' "$WARNINGS_FILE"
fi
{
  echo "Matchy dependency freshness report"
  echo "Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "Source: pip list --outdated --format=columns"
  echo ""
} > "$TEXT_REPORT"

total_updates=0
major_updates=0
json_items=""
while IFS= read -r line; do
  [[ -n "$line" ]] || continue
  package="$(awk '{print $1}' <<<"$line")"
  current="$(awk '{print $2}' <<<"$line")"
  latest="$(awk '{print $3}' <<<"$line")"
  current_major="$(major_from_version "$current")"
  latest_major="$(major_from_version "$latest")"
  is_major="false"
  if [[ "$latest_major" -gt "$current_major" ]]; then
    is_major="true"
    major_updates=$((major_updates + 1))
  fi
  total_updates=$((total_updates + 1))
  printf -- "- %s %s -> %s (major_update=%s)\n" "$package" "$current" "$latest" "$is_major" >> "$TEXT_REPORT"
  if [[ -n "$json_items" ]]; then
    json_items+=","
  fi
  json_items+="{\"package\":\"${package}\",\"current\":\"${current}\",\"latest\":\"${latest}\",\"major_update\":${is_major}}"
done < "$UPDATES_FILE"
if [[ "$total_updates" -eq 0 ]]; then
  echo "No updates available." >> "$TEXT_REPORT"
fi

#R015: Emit machine-readable JSON report with aggregate counts for CI and auditing.
{
  echo "{"
  echo "  \"generated_by\": \"04_run_dependency_freshness_checks.sh\","
  echo "  \"total_updates\": ${total_updates},"
  echo "  \"major_updates\": ${major_updates},"
  echo "  \"fail_on_updates\": ${FAIL_ON_ANY},"
  echo "  \"fail_on_major\": ${FAIL_ON_MAJOR},"
  echo "  \"modules\": [${json_items}]"
  echo "}"
} > "$JSON_REPORT"

status=0
if [[ "$FAIL_ON_ANY" == "true" ]] && [[ "$total_updates" -gt 0 ]]; then
  #R020: Enforce freshness gate on any available dependency update by default.
  echo "❌ Dependency updates detected (${total_updates}) with DEPENDENCY_FAIL_ON_UPDATES=true"
  status=1
fi
#R020: Support optional major-version gating for CI freshness enforcement.
if [[ "$FAIL_ON_MAJOR" == "true" ]] && [[ "$major_updates" -gt 0 ]]; then
  echo "❌ Major dependency updates detected (${major_updates}) with DEPENDENCY_FAIL_ON_MAJOR=true"
  status=1
fi

#R025: Print concise operator-readable status with report locations and update counts.
echo "✅ Dependency freshness checks completed."
echo "   - text report: ${TEXT_REPORT}"
echo "   - json report: ${JSON_REPORT}"
echo "   - updates: ${total_updates}"
echo "   - major updates: ${major_updates}"
if [[ "$total_updates" -gt 0 ]]; then
  echo "   - available updates:"
  awk '/^- / { printf "     %s\n", $0 }' "$TEXT_REPORT"
fi
exit "$status"
