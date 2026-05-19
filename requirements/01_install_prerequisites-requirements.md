# Install Prerequisites Requirements

## Scope

Applies to `01_install_prerequisites.sh`.

R001  Statement: Run with `bash` in strict fail-fast mode.
Design: Use `set -euo pipefail` and exit non-zero on unrecoverable failures.
Tests:
- R001-T01: Force a failing command and verify installer exits non-zero.

R005  Statement: Verify Homebrew exists before Homebrew package actions.
Design: Check `brew` on `PATH`; print install guidance when missing.
Tests:
- R005-T01: Run with `brew` unavailable and verify clear failure guidance.

R010  Statement: Ensure required CLI formulas are available for Matchy workflows.
Design: Install/check `shellcheck`, `semgrep`, `gitleaks`, `detect-secrets`, `ruff`, `bandit`, `pip-audit`, and `bats` (via `bats-core`) through Homebrew.
Tests:
- R010-T01: Run without these commands and verify Homebrew install attempts.
- R010-T02: Rerun with tools already present and verify idempotent success.

R015  Statement: Emit concise operator-readable status output.
Design: Print phase output for prerequisite checks and completion guidance.
Tests:
- R015-T01: Run installer and verify status lines plus completion output.

R020  Statement: Keep installer idempotent across reruns.
Design: Skip install/setup steps when dependencies are already satisfied.
Tests:
- R020-T01: Run installer twice and verify the second run performs no unnecessary installs.

R025  Statement: Print final readiness guidance for local development.
Design: End with success output that references Matchy numbered commands (`./02_create_venv.sh`, `./03_load_requirements.sh`, `./05_run_unit_tests.sh`, `./06_run_security_checks.sh`, `./07_run_av_checks.sh`, `./08_run_matchy_api.py`).
Tests:
- R025-T01: On successful run, verify final guidance includes those commands.

R030  Statement: Treat `1psa` as optional advisory in this bootstrap script.
Design: If `1psa` is missing, print advisory output without failing the installer.
Tests:
- R030-T01: Run with no `1psa` on `PATH` and verify success with advisory message.

## Changelog

- 2026-05-12: Reswizzled from Xcode/Swift setup to Matchy shell-tool bootstrap and script-oriented guidance.
