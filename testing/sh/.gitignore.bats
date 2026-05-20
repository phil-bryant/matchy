#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R020-T01 #R025-T01 #R030-T01 #R030-T02 #R035-T01 #R035-T02

@test ".build artifacts are ignored and hidden from git status" {
  #R001: Build output must be ignored recursively.
  #R020: Ignored build paths must not be tracked.
  #R025: Regression guard for `.build/` and `.security-reports/` ignore behavior.
  tmp_path=".build/traceability-ignore-test-$$.tmp"
  cleanup() {
    if [ -f "$tmp_path" ]; then
      trash_dir="${HOME}/.Trash/piston-gitignore-bats-$$"
      mkdir -p "$trash_dir"
      mv "$tmp_path" "$trash_dir/traceability-ignore-test.tmp"
    fi
  }
  trap cleanup EXIT
  mkdir -p ".build"
  printf "traceability-fixture\n" > "$tmp_path"

  run git check-ignore -q "$tmp_path"
  [ "$status" -eq 0 ]

  run git status --porcelain -- "$tmp_path"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "xcode local metadata remains ignored" {
  #R005: User-local Xcode metadata must be excluded from version control.
  run git check-ignore -v "DerivedData/example/index"
  [ "$status" -eq 0 ]
  [[ "$output" == *".gitignore"* ]]
}

@test "security report artifacts remain ignored" {
  #R025: Security report outputs must remain untracked.
  run git check-ignore -v ".security-reports/security-summary.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *".gitignore"* ]]
}

@test "project source and shared config stay trackable" {
  #R010: Source and shared package metadata must stay tracked.
  #R015: Cleanup should happen via cached removals, not local deletion.
  run git check-ignore -q "Package.swift"
  [ "$status" -ne 0 ]
}

@test "project virtual environment remains ignored" {
  #R030: Venv directory must be excluded from version control.
  repo_basename="$(basename "$PWD")"
  venv_probe="${repo_basename}-venv/lib/traceability-ignore-probe-$$.tmp"
  run git check-ignore -v "$venv_probe"
  [ "$status" -eq 0 ]
  [[ "$output" == *".gitignore"* ]]
  [[ "$output" == *"*-venv/"* ]]
}

@test "python bytecode caches remain ignored" {
  #R035: __pycache__ directories and .pyc files must be excluded from version control.
  pyc_probe="matchy/__pycache__/module.cpython-312.pyc"
  run git check-ignore -v "$pyc_probe"
  [ "$status" -eq 0 ]
  [[ "$output" == *".gitignore"* ]]
  [[ "$output" == *"__pycache__/"* ]] || [[ "$output" == *"*.pyc"* ]]
}
