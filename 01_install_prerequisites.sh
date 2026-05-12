#!/bin/bash
umask 007
#R001: Enforce strict fail-fast shell behavior.
set -euo pipefail

#R015: Emit concise setup banner.
echo "Matchy prerequisites"

#R005: Require Homebrew before formula installs.
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required."
  exit 1
fi

ensure_formula() {
  #R010: Install/check required CLI formulas for Matchy tooling.
  local formula="$1"
  local cmd="${2:-$formula}"
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "✓ ${cmd}"
    return
  fi
  brew install "$formula"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Failed to install ${formula}"
    exit 1
  fi
}

#R020: Keep prerequisite installation idempotent across reruns.
ensure_formula shellcheck
ensure_formula semgrep
ensure_formula gitleaks
ensure_formula detect-secrets
ensure_formula ruff
ensure_formula bandit
ensure_formula pip-audit
ensure_formula bats-core bats

#R030: Treat 1psa as optional advisory, not a hard requirement.
if ! command -v 1psa >/dev/null 2>&1; then
  echo "1psa is recommended for secrets lookup but is not installed."
fi

#R025: Print next-step guidance for local Matchy workflow.
echo "✅ Prerequisites complete."
echo "Next commands:"
echo "- ./02_create_venv.sh"
echo "- ./03_load_requirements.sh"
echo "- make test"
echo "- make sast"
echo "- make run"
