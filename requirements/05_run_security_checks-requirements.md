# Run Security Checks Requirements

## Scope

Applies to `05_run_security_checks.sh`.

R001  Statement: Run in strict fail-fast shell mode from repository root.
Design: Use `set -euo pipefail`, resolve the script directory from `${BASH_SOURCE[0]}`, and `cd` to that directory before running scanners.
Tests:
- Invoke script from a non-repo working directory and verify reports are still emitted under repo-relative paths.

R005  Statement: Persist security reports under deterministic output paths.
Design: Always create `${SECURITY_REPORT_DIR:-./.security-reports}` and write lane artifacts there.
Tests:
 - Run script and verify report directory is created.

R010  Statement: Fail clearly when an enabled lane is missing required tooling.
Design: Validate required commands with a dedicated checker and return actionable tool-specific error output for `shellcheck`, `semgrep`, `gitleaks`, `detect-secrets`, `ruff`, `bandit`, and `pip-audit`.
Tests:
 - Remove each required tool from `PATH` and verify explicit missing-command failure output.

R015  Statement: Run ShellCheck lane and persist JSON output.
Design: Run `shellcheck -f json` across discovered shell targets (`*.sh`, `testing/*.bats`, `testing/sh/*.bats`) and write `shellcheck.json`.
Tests:
 - Stub ShellCheck and verify `shellcheck.json` is written.

R020  Statement: Run Semgrep and Ruff in JSON mode and persist report artifacts.
Design: Execute `semgrep scan --config auto --json --output <file>` to write `semgrep.json` and `ruff check --output-format json` to write `ruff.json`.
Tests:
 - Stub Semgrep and verify `semgrep.json` is written.

R025  Statement: Run secret, vulnerability, and Python security lanes and persist report artifacts.
Design: Execute `gitleaks detect ...` (`gitleaks.json`), `detect-secrets scan --all-files` (`detect-secrets.json`), `bandit -r . -f json -o <file>` (`bandit.json`), and `pip-audit --format json --output <file>` (`pip-audit.json`).
Tests:
 - Stub each lane and verify `gitleaks.json`, `detect-secrets.json`, `bandit.json`, and `pip-audit.json` are written.

R030  Statement: Emit deterministic completion output.
Design: Print a final success line containing the report directory path.
Tests:
 - Run script and verify output includes `Security checks completed. Reports:`.

R035  Statement: Print standardized per-lane security tool headers.
Design: Each enabled lane prints a manifold-style header block including tool name, short explainer lines, and URL.
Tests:
 - Run script with stubbed tools and verify output includes `Security Tool: ShellCheck` and matching header border formatting.

R040  Statement: Print explicit per-lane running indicators.
Design: Emit operator-facing lane start indicators like `▶ Running ShellCheck` before each scanner executes.
Tests:
 - Run script with stubbed tools and verify output includes `▶ Running ShellCheck`.

R045  Statement: Isolate pip-audit cache to prevent stale cache deserialization warnings without suppressing output.
Design: Set and export `PIP_CACHE_DIR` to a run-local path under `${SECURITY_REPORT_DIR:-./.security-reports}` before invoking `pip-audit`.
Tests:
 - Stub `pip-audit` to record `PIP_CACHE_DIR` and verify it points to `${REPORT_DIR}/.pip-cache`.
 - Verify the cache directory is created and pip-audit output remains visible (no `/dev/null` suppression for the lane).

## Changelog

- 2026-05-12: Added isolated pip-audit cache requirement to prevent cachecontrol deserialization warnings without suppression.
- 2026-05-12: Expanded Matchy security lanes to include detect-secrets, ruff, bandit, and pip-audit.
- 2026-05-12: Added requirements for standardized tool headers and running indicators.
