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
Design: Validate required commands with a dedicated checker and return actionable tool-specific error output.
Tests:
 - Remove each required tool from `PATH` and verify explicit missing-command failure output.

R015  Statement: Run ShellCheck lane and persist JSON output.
Design: Run `shellcheck -f json` across discovered shell targets (`*.sh`, `testing/*.bats`, `testing/sh/*.bats`) and write `shellcheck.json`.
Tests:
 - Stub ShellCheck and verify `shellcheck.json` is written.

R020  Statement: Run Semgrep in JSON mode and persist report artifacts.
Design: Execute `semgrep --config auto --json --output <file>` and write `semgrep.json`.
Tests:
 - Stub Semgrep and verify `semgrep.json` is written.

R025  Statement: Run Gitleaks and persist report artifacts.
Design: Execute `gitleaks detect --source . --no-banner --report-format json --report-path <file>` and write `gitleaks.json`.
Tests:
 - Stub Gitleaks and verify `gitleaks.json` is written.

R030  Statement: Emit deterministic completion output.
Design: Print a final success line containing the report directory path.
Tests:
 - Run script and verify output includes `Security checks completed. Reports:`.

## Changelog

- 2026-05-12: Reswizzled from copied multi-tool policy to Matchy’s current shellcheck/semgrep/gitleaks script behavior.
