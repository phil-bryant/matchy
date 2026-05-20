# Run Security Checks Requirements

## Scope

Applies to `06_run_security_checks.sh`.

R001  Statement: Run in strict fail-fast shell mode from repository root.
Design: Use `set -euo pipefail`, resolve the script directory from `${BASH_SOURCE[0]}`, and `cd` to that directory before running scanners.
Tests:
- R001-T01: Invoke script from a non-repo working directory and verify reports are still emitted under repo-relative paths.

R005  Statement: Persist security reports under deterministic output paths.
Design: Always create `${SECURITY_REPORT_DIR:-./.security-reports}` and write lane artifacts there.
Tests:
- R005-T01: Run script and verify report directory is created.

R010  Statement: Fail clearly when an enabled lane is missing required tooling.
Design: Validate required commands with a dedicated checker and return actionable tool-specific error output for `shellcheck`, `semgrep`, `gitleaks`, `detect-secrets`, `ruff`, `bandit`, and `pip-audit`. Only require and run tools listed in `${SECURITY_RUN_LANES}` (comma-separated; default all seven lanes).
Tests:
- R010-T01: Remove each required tool from `PATH` and verify explicit missing-command failure output.

R015  Statement: Run ShellCheck lane and persist JSON output.
Design: Run `shellcheck -f json` across discovered shell targets (`*.sh`, `tests/*.bats`, `tests/sh/*.bats`) and write `shellcheck.json`.
Tests:
- R015-T01: Stub ShellCheck and verify `shellcheck.json` is written.

R020  Statement: Run Semgrep and Ruff in JSON mode and persist report artifacts.
Design: Execute `semgrep scan --config auto --json --output <file>` to write `semgrep.json` and `ruff check --output-format json` to write `ruff.json`.
Tests:
- R020-T01: Stub Semgrep and verify `semgrep.json` is written.

R025  Statement: Run secret, vulnerability, and Python security lanes and persist report artifacts.
Design: Execute `gitleaks detect ...` (`gitleaks.json`), `detect-secrets scan --all-files` (`detect-secrets.json`), `bandit -ll -r . -f json -o <file>` (`bandit.json`) with severity floor MEDIUM (LOW subprocess false positives on validated `1psa` argv are out of scope), and `pip-audit --format json --output <file>` (`pip-audit.json`).
Tests:
- R025-T01: Stub each lane and verify `gitleaks.json`, `detect-secrets.json`, `bandit.json`, and `pip-audit.json` are written.

R030  Statement: Emit per-lane and overall pass/fail output that reflects real findings.
Design: After all lanes complete, print one `✅ PASS:` or `❌ FAIL:` line per tool based on report findings and lane exit codes, write `security-summary.json`, then print a final overall `✅ Security checks PASSED` or `❌ Security checks FAILED` line containing the report directory path. Exit non-zero when any lane fails.
Tests:
- R030-T01: Run script with clean stubbed tools and verify output includes `✅ PASS:` lines and `✅ Security checks PASSED. Reports:`.
- R030-T02: Run script with a stubbed lane that reports findings and verify output includes `❌ FAIL:` for that lane and `❌ Security checks FAILED. Reports:` with non-zero exit status.

R050  Statement: Gate overall status on findings and execution errors.
Design: Honor `SECURITY_FAIL_ON_FINDINGS` (default `true`). Count findings from each lane JSON artifact and treat execution errors (invalid/missing reports or tool exit codes above tool-specific thresholds) as lane failures.
Tests:
- R050-T01: Stub ShellCheck to exit 1 with a non-empty JSON report and verify the script exits non-zero.

R035  Statement: Print standardized per-lane security tool headers.
Design: Each enabled lane prints a manifold-style header block including tool name, short explainer lines, and URL.
Tests:
- R035-T01: Run script with stubbed tools and verify output includes `Security Tool: ShellCheck` and matching header border formatting.

R040  Statement: Print explicit per-lane running indicators.
Design: Emit operator-facing lane start indicators like `▶ Running ShellCheck` before each scanner executes.
Tests:
- R040-T01: Run script with stubbed tools and verify output includes `▶ Running ShellCheck`.

R045  Statement: Isolate pip-audit cache to prevent stale cache deserialization warnings without suppressing output.
Design: Set and export `PIP_CACHE_DIR` to a run-local path under `${SECURITY_REPORT_DIR:-./.security-reports}` before invoking `pip-audit`.
Tests:
- R045-T01: Stub `pip-audit` to record `PIP_CACHE_DIR` and verify it points to `${REPORT_DIR}/.pip-cache`.
- R045-T02: Verify the cache directory is created and pip-audit output remains visible (no `/dev/null` suppression for the lane).

R055  Statement: Print human-readable findings to the console after each lane completes.
Design: Parse each lane JSON artifact and print operator-facing finding lines before the next tool header. ShellCheck, Semgrep, Ruff, and Bandit emit structured finding lists; detect-secrets emits findings with source lines; Gitleaks and pip-audit emit concise warning lines when native CLI output is insufficient. Emit nothing extra when a lane report contains zero findings.
Tests:
- R055-T01: Stub ShellCheck with one finding and verify output includes `ShellCheck findings` and file/line detail before the next `Security Tool:` header.
- R055-T02: Stub Ruff with one finding and verify output includes `Ruff findings`.
- R055-T03: Stub Bandit with one finding and verify output includes `Bandit findings`.

R060  Statement: Run detect-secrets with artifact excludes, heartbeat status, and blocking completion.
Design: Execute `detect-secrets scan --all-files --exclude-files` with excludes for `.git`, `.security-reports`, `.parallel-checks-reports`, `.cursor`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, `matchy-venv`, `.venv`, `build`, `dist`, and `mutants`. When `${DETECT_SECRETS_USE_BACKGROUND_WAIT:-true}` is `true`, run the scan in the background, use `ps`-based liveness for heartbeat polling (not `kill -0` on exited PIDs), print elapsed-time heartbeat lines every `${DETECT_SECRETS_HEARTBEAT_SECONDS:-15}` seconds while it runs, and block until the scan process exits. When `DETECT_SECRETS_USE_BACKGROUND_WAIT=false`, run the scan in the foreground without heartbeat polling. After either mode completes, print every finding with its matched source line sorted by file and line.
Tests:
- R060-T01: Stub a long-running detect-secrets execution with background wait enabled and verify a heartbeat line appears before the next tool header.
- R060-T02: Stub detect-secrets findings output and verify each finding prints its source line before the next tool header.

R065  Statement: Allow selective lane execution for faster local and CI subsets.
Design: Honor `SECURITY_RUN_LANES` as a comma-separated subset of `shellcheck`, `semgrep`, `gitleaks`, `detect-secrets`, `ruff`, `bandit`, and `pip-audit`. Skip `require_command`, lane runners, and per-lane pass/fail lines for lanes not listed. Gate evaluation (`emit_lane_results_and_gate`) considers only lanes recorded in `lane-exits.env`.
Tests:
- R065-T01: Run with `SECURITY_RUN_LANES=pip-audit` and verify only pip-audit executes.

## Changelog

- 2026-05-20: Split bats into `06_run_security_checks_{core,findings,detect_secrets}.bats`; add `DETECT_SECRETS_USE_BACKGROUND_WAIT` for foreground test runs.
- 2026-05-20: Add `SECURITY_RUN_LANES` subset execution and configurable `DETECT_SECRETS_HEARTBEAT_SECONDS`.
- 2026-05-20: Renamed repository test directory from `testing/` to `tests/`.
- 2026-05-19: Expand detect-secrets excludes for IDE/cache dirs; Bandit gates MEDIUM+ (`-ll`); heartbeat uses `ps` liveness.
- 2026-05-19: Require per-lane console findings output and detect-secrets heartbeat/exclude behavior.
- 2026-05-19: Require per-lane pass/fail output and overall gate based on findings instead of unconditional success messaging.
- 2026-05-12: Added isolated pip-audit cache requirement to prevent cachecontrol deserialization warnings without suppression.
- 2026-05-12: Expanded Matchy security lanes to include detect-secrets, ruff, bandit, and pip-audit.
- 2026-05-12: Added requirements for standardized tool headers and running indicators.
