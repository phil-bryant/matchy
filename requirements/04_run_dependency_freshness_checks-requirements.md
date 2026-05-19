# Run Dependency Freshness Checks Requirements

## Scope

Applies to `04_run_dependency_freshness_checks.sh` and dependency freshness reporting for this Python repository.

R001  Statement: Run from repository root regardless of caller working directory.
Design: Resolve script directory from `${BASH_SOURCE[0]}` and `cd` into it before any report or module operations.
Tests:
- R001-T01: Run from a non-root directory and verify reports are still written under repository-root `.security-reports`.

R005  Statement: Select the pip binary predictably and fail clearly when unavailable.
Design: Use `DEPENDENCY_CHECK_PIP_BIN` when provided, default to `pip`, and fail with actionable output when command resolution fails.
Tests:
- R005-T01: Run with a stubbed `pip` on `PATH` and verify the selected binary is reported.
- R005-T02: Set `DEPENDENCY_CHECK_PIP_BIN` to a missing command and verify non-zero failure.

R010  Statement: Discover direct dependency updates and always emit a text report.
Design: Execute `pip list --outdated --format=columns`, normalize package rows, and write `dependency-freshness.txt` with one line per update.
Tests:
- R010-T01: Run with update-producing stub output and verify text report includes package update entries.

R015  Statement: Emit machine-readable dependency freshness JSON.
Design: Always write `dependency-freshness.json` including total update count, major update count, and per-module current/latest version data.
Tests:
- R015-T01: Run with update-producing stub output and verify JSON report contains counts and module fields.

R020  Statement: Enforce dependency freshness failures when direct updates are available.
Design: When `DEPENDENCY_FAIL_ON_UPDATES=true` (default), exit non-zero if any direct dependency update is available. Keep `DEPENDENCY_FAIL_ON_MAJOR` as an additional gate for major-version boundaries.
Tests:
- R020-T01: Run with updates present and default configuration and verify non-zero exit.
- R020-T02: Run with updates present and `DEPENDENCY_FAIL_ON_UPDATES=false` and verify zero exit unless other enabled gates fail.
- R020-T03: Run with major update present and `DEPENDENCY_FAIL_ON_MAJOR=true` and verify non-zero exit.

R025  Statement: Emit concise status output for operators and CI logs.
Design: Print selected binary, report file paths, and update counters at completion for quick run diagnostics.
Tests:
- R025-T01: Run script successfully and verify output includes report paths plus update and major-update counts.

## Changelog

- 2026-05-18: Fully reswizzled to Matchy Python dependency freshness via `pip list --outdated`.
- 2026-05-16: Numbered test bullets with R###-T## scheme.
- 2026-05-08: Imported baseline dependency freshness flow from Valve before Matchy-specific reswizzle.
