# Install Prerequisites Requirements

## Scope

Applies to `01_install_prerequisites.sh`.

R001  Statement: Run with `bash` in strict fail-fast mode.
Design: Use `set -euo pipefail` and exit non-zero on unrecoverable failures.
Tests:
- Force a failing command and verify installer exits non-zero.

R005  Statement: Verify Homebrew exists before Homebrew package actions.
Design: Check `brew` on `PATH`; print install guidance when missing.
Tests:
- Run with `brew` unavailable and verify clear failure guidance.

R010  Statement: Ensure required CLI formulas are available for Matchy workflows.
Design: Install/check `shellcheck`, `semgrep`, `gitleaks`, `detect-secrets`, `ruff`, `bandit`, `pip-audit`, and `bats` (via `bats-core`) through Homebrew.
Tests:
 - Run without these commands and verify Homebrew install attempts.
 - Rerun with tools already present and verify idempotent success.

R015  Statement: Emit concise operator-readable status output.
Design: Print phase output for prerequisite checks and completion guidance.
Tests:
 - Run installer and verify status lines plus completion output.

R020  Statement: Keep installer idempotent across reruns.
Design: Skip install/setup steps when dependencies are already satisfied.
Tests:
- Run installer twice and verify the second run performs no unnecessary installs.

R025  Statement: Print final readiness guidance for local development.
Design: End with success output that references Matchy commands (`./02_create_venv.sh`, `./03_load_requirements.sh`, `make test`, `make sast`, `make run`).
Tests:
 - On successful run, verify final guidance includes those commands.

R030  Statement: Treat `1psa` as optional advisory in this bootstrap script.
Design: If `1psa` is missing, print advisory output without failing the installer.
Tests:
 - Run with no `1psa` on `PATH` and verify success with advisory message.

## Changelog

- 2026-05-12: Reswizzled from Xcode/Swift setup to Matchy shell-tool bootstrap and script-oriented guidance.
