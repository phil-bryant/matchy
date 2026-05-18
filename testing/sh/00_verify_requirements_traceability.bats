#!/usr/bin/env bats

# R090 numbered-tag parity supplements for fixture scenarios covered below.
#R015-T02
#R030-T02
#R035-T02
#R040-T02
#R045-T02
#R050-T02
#R050-T03
#R050-T04
#R060-T02
#R065-T02
#R065-T03
#R070-T02
#R075-T02
#R080-T02
#R085-T02

make_traceability_fixture() {
  local fixture_root="$1" mode="$2"
  mkdir -p "${fixture_root}/requirements" "${fixture_root}/testing/sh"
  cat > "${fixture_root}/requirements/fixture-requirements.md" <<'EOF'
# Fixture Requirements

## Scope

Applies to `fixture.sh`.

R001  Statement: First behavior.
Tests:
- R001-T01: First behavior test trace.
R005  Statement: Second behavior.
Tests:
- R005-T01: Second behavior test trace.
EOF
  if [ "$mode" = "bundled" ]; then
    cat > "${fixture_root}/fixture.sh" <<'EOF'
#!/bin/bash
# #R001 #R005 #R010
echo "fixture"
EOF
  fi
  if [ "$mode" = "unscoped" ]; then
    cat > "${fixture_root}/fixture.sh" <<'EOF'
#!/bin/bash
# #R001
# #R005
echo "fixture"
EOF
  fi
  if [ "$mode" = "scoped" ]; then
    cat > "${fixture_root}/fixture.sh" <<'EOF'
#!/bin/bash
# #R001: First behavior.
echo "first"
# #R005: Second behavior.
echo "second"
EOF
  fi
  cat > "${fixture_root}/testing/sh/fixture.bats" <<'EOF'
#!/usr/bin/env bats

@test "fixture requirement tags" {
  #R001-T01: First behavior test trace.
  #R005-T01: Second behavior test trace.
  #R001: First behavior test trace.
  #R005: Second behavior test trace.
  [ 1 -eq 1 ]
}
EOF
  chmod +x "${fixture_root}/fixture.sh"
}

make_go_module_traceability_fixture() {
  local fixture_root="$1"
  mkdir -p "${fixture_root}/requirements" "${fixture_root}/testing/sh"
  cat > "${fixture_root}/requirements/fixture-requirements.md" <<'EOF'
# Fixture Requirements

## Scope

Applies to `fixture.sh`.

R001  Statement: First behavior.
Tests:
- R001-T01: First behavior test trace.
EOF
  cat > "${fixture_root}/fixture.sh" <<'EOF'
#!/bin/bash
# #R001: First behavior.
echo "fixture"
EOF
  cat > "${fixture_root}/testing/sh/fixture.bats" <<'EOF'
#!/usr/bin/env bats

@test "fixture requirement tags" {
  #R001-T01: First behavior test trace.
  #R001: First behavior test trace.
  [ 1 -eq 1 ]
}
EOF
  cat > "${fixture_root}/go.mod" <<'EOF'
module fixture

go 1.24
EOF
  chmod +x "${fixture_root}/fixture.sh"
}

make_go_source_traceability_fixture() {
  local fixture_root="$1" with_tag="$2"
  mkdir -p "${fixture_root}/requirements/pkg" "${fixture_root}/pkg"
  cat > "${fixture_root}/go.mod" <<'EOF'
module fixture

go 1.24
EOF
  cat > "${fixture_root}/requirements/pkg/example-requirements.md" <<'EOF'
# Example Go Requirements

## Scope

Applies to `pkg/example.go`.

R001  Statement: Example behavior.
Tests:
- R001-T01: Example Go test tag discovered from package test file.
EOF
  cat > "${fixture_root}/pkg/example.go" <<'EOF'
package pkg

// #R001: Example behavior implementation.
func Example() string { return "ok" }
EOF
  if [ "${with_tag}" = "with-tag" ]; then
    cat > "${fixture_root}/pkg/example_test.go" <<'EOF'
package pkg

import "testing"

func TestExample(t *testing.T) {
  // #R001-T01: Example Go test tag discovered from package test file.
  // #R001: Example Go test tag discovered from package test file.
  if Example() != "ok" {
    t.Fatalf("unexpected")
  }
}
EOF
  else
    cat > "${fixture_root}/pkg/example_test.go" <<'EOF'
package pkg

import "testing"

func TestExample(t *testing.T) {
  if Example() != "ok" {
    t.Fatalf("unexpected")
  }
}
EOF
  fi
}

make_python_lane_traceability_fixture() {
  local fixture_root="$1"
  mkdir -p "${fixture_root}/requirements" "${fixture_root}/testing/sh"
  cat > "${fixture_root}/requirements/python-requirements.md" <<'EOF'
# Python Lane Fixture Requirements

## Scope

Applies to `fixture.py`.

R001  Statement: Python fixture behavior.
Tests:
- R001-T01: Python fixture behavior trace.
EOF
  cat > "${fixture_root}/fixture.py" <<'EOF'
# #R001: Python fixture behavior implementation.
print("fixture")
EOF
  cat > "${fixture_root}/testing/sh/python-lane.bats" <<'EOF'
#!/usr/bin/env bats
@test "python lane placeholder" {
  #R001-T01: Python fixture behavior trace.
  #R001: Python fixture behavior trace.
  [ 1 -eq 1 ]
}
EOF
}

make_numbered_traceability_mismatch_fixture() {
  local fixture_root="$1"
  local HASH="#"
  mkdir -p "${fixture_root}/requirements" "${fixture_root}/testing/sh"
  cat > "${fixture_root}/requirements/fixture-requirements.md" <<'EOF'
# Numbered Traceability Fixture Requirements

## Scope

Applies to `fixture.sh`.

R001  Statement: Numbered traceability fixture behavior.
Tests:
- R001-T01: Numbered traceability fixture baseline.
- R001-T04: Numbered traceability fixture intentionally skips T03.
EOF
  cat > "${fixture_root}/fixture.sh" <<'EOF'
#!/bin/bash
# #R001: Numbered traceability fixture implementation.
echo "fixture"
EOF
  cat > "${fixture_root}/testing/sh/fixture.bats" <<EOF
#!/usr/bin/env bats

@test "fixture numbered traceability tags" {
  #R001-T01: Numbered traceability fixture baseline.
  ${HASH}R001-T03: Numbered traceability fixture extra tag not declared in requirements.
  #R001: Numbered traceability fixture coverage.
  [ 1 -eq 1 ]
}
EOF
  chmod +x "${fixture_root}/fixture.sh"
}

@test "Traceability tags for verifier requirements" {
  #R001-T01: Strict mode and temp file setup requirement coverage.
  #R005-T01: Default recursive requirements discovery coverage.
  #R010-T01: Requirements-to-source mapping coverage.
  #R015-T01: Missing mapping/source failure messaging coverage.
  #R020-T01: Requirement ID parsing coverage.
  #R025-T01: Source #R tag parsing coverage.
  #R030-T01: Missing/extra set-difference reporting coverage.
  #R035-T01: Pass/fail exit semantics coverage.
  #R040-T01: Numbered script requirements coverage checks.
  #R045-T01: Numbered requirements scope alignment checks.
  #R050-T01: Requirement-to-test discovery coverage.
  #R050-T04: Missing testing/py lane for python source triggers explicit failure.
  #R055-T01: Discovered-test #R tag extraction coverage.
  #R060-T01: Missing test-traceability ID failure coverage.
  #R065-T01: Anti-cheat header-bundle and scoped comment enforcement coverage.
  #R070-T01: Requirements-only mode traceability-skip coverage.
  #R075-T01: Go package _test.go coverage enforcement in full-run mode.
  #R080-T01: Go source scoped requirements discover sibling _test.go files.
  #R085-T01: Repository software files without requirements coverage are auto-detected.
  #R090-T01: Test file with #R001 but no #R001-T01 triggers numbered-tag failure.
  #R090-T02: Adding #R001-T01 to test file makes the check pass.
  #R090-T03: 1:1 mismatch fixture reports both missing-in-tests and missing-in-requirements sections.
  #R090-T04: Malformed tests bullet missing Rxxx-T## prefix triggers malformed-bullet failure output.
  #R090-T05: Requirements-only doc skips the numbered-tag check.
  #R001: Strict mode and temp file setup requirement coverage.
  #R005: Default recursive requirements discovery coverage.
  #R010: Requirements-to-source mapping coverage.
  #R015: Missing mapping/source failure messaging coverage.
  #R020: Requirement ID parsing coverage.
  #R025: Source #R tag parsing coverage.
  #R030: Missing/extra set-difference reporting coverage.
  #R035: Pass/fail exit semantics coverage.
  #R040: Numbered script requirements coverage checks.
  #R045: Numbered requirements scope alignment checks.
  #R050: Requirement-to-test discovery coverage.
  #R055: Discovered-test #R tag extraction coverage.
  #R060: Missing test-traceability ID failure coverage.
  #R065: Anti-cheat header-bundle and scoped comment enforcement coverage.
  #R070: Requirements-only mode traceability-skip coverage.
  #R075: Go package _test.go coverage enforcement in full-run mode.
  #R080: Go source scoped requirements discover sibling _test.go files.
  #R085: Repository software files without requirements coverage are auto-detected.
  #R090: Numbered test tag enforcement coverage.
  [ 1 -eq 1 ]
}

@test "Fails when header-bundled tags are used near file top" {
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_traceability_fixture "${fixture_root}" "bundled"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/00_verify_requirements_traceability.sh"
  run /bin/bash "${fixture_root}/00_verify_requirements_traceability.sh" "${fixture_root}/requirements/fixture-requirements.md" "${fixture_root}/fixture.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"FAIL (anti-cheat)"* ]]
}

@test "Fails when IDs exist only as unscoped set-membership tags" {
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_traceability_fixture "${fixture_root}" "unscoped"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/00_verify_requirements_traceability.sh"
  run /bin/bash "${fixture_root}/00_verify_requirements_traceability.sh" "${fixture_root}/requirements/fixture-requirements.md" "${fixture_root}/fixture.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Missing scoped #R comments"* ]]
}

@test "Passes when requirement IDs are scoped with #Rxxx: comments" {
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_traceability_fixture "${fixture_root}" "scoped"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/00_verify_requirements_traceability.sh"
  run /bin/bash "${fixture_root}/00_verify_requirements_traceability.sh" "${fixture_root}/requirements/fixture-requirements.md" "${fixture_root}/fixture.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS (test-traceability)"* ]]
}

@test "Requirements-only mode skips source/test traceability checks" {
  local fixture_root
  fixture_root="$(mktemp -d)"
  mkdir -p "${fixture_root}/requirements"
  cat > "${fixture_root}/requirements/phase-requirements.md" <<'EOF'
# Phase Requirements

## Scope

Requirements-only mode: true.

R001  Statement: Placeholder requirement while implementation is pending.
EOF
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS (requirements-only)"* ]]
}

@test "Fails full-run mode when repository software has no requirements coverage" {
  #R085
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_traceability_fixture "${fixture_root}" "scoped"
  cat > "${fixture_root}/orphan.sh" <<'EOF'
#!/bin/bash
echo "orphan"
EOF
  chmod +x "${fixture_root}/orphan.sh"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh'"
  [ "$status" -ne 0 ]
  [[ "$output" == *"repository software files missing requirements coverage"* ]]
  [[ "$output" == *"orphan.sh"* ]]
}

@test "Fails full-run mode when go module package has no _test.go files" {
  #R075
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_go_module_traceability_fixture "${fixture_root}"
  mkdir -p "${fixture_root}/internal/notested"
  cat > "${fixture_root}/internal/notested/notested.go" <<'EOF'
package notested

func Value() string { return "ok" }
EOF
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh'"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Go source files without peer *_test.go files"* ]]
  [[ "$output" == *"internal/notested/notested.go"* ]]
}

@test "Passes full-run mode when go module packages include _test.go files" {
  #R075
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_go_module_traceability_fixture "${fixture_root}"
  mkdir -p "${fixture_root}/internal/tested"
  cat > "${fixture_root}/requirements/go-tested-requirements.md" <<'EOF'
# Go Tested Requirements

## Scope

Applies to `internal/tested/tested.go`.

R900  Statement: Go tested fixture behavior.
Tests:
- R900-T01: Go tested fixture behavior validation.
EOF
  cat > "${fixture_root}/internal/tested/tested.go" <<'EOF'
package tested

// #R900: Go tested fixture behavior implementation.
func Value() string { return "ok" }
EOF
  cat > "${fixture_root}/internal/tested/tested_test.go" <<'EOF'
package tested

import "testing"

func TestValue(t *testing.T) {
  // #R900-T01: Go tested fixture behavior validation.
  // #R900: Go tested fixture behavior validation.
  if Value() != "ok" {
    t.Fatalf("unexpected")
  }
}
EOF
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Go source test coverage complete"* ]]
}

@test "Fails when discovered Go package tests do not include requirement tags" {
  #R080
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_go_source_traceability_fixture "${fixture_root}" "without-tag"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh' './requirements/pkg/example-requirements.md' './pkg/example.go'"
  [ "$status" -ne 0 ]
  [[ "$output" == *"missing tagged tests for requirement IDs"* ]]
}

@test "Fails when python source lacks required testing/py lane file" {
  #R050-T04: Missing testing/py lane for python source triggers explicit failure.
  #R050
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_python_lane_traceability_fixture "${fixture_root}"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh'"
  [ "$status" -ne 0 ]
  [[ "$output" == *"FAIL (python-test-lane)"* ]]
  [[ "$output" == *"fixture.py -> expected testing/py/test_fixture.py"* ]]
}

@test "Passes when Go source requirements discover sibling tagged _test.go files" {
  #R080
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_go_source_traceability_fixture "${fixture_root}" "with-tag"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh' './requirements/pkg/example-requirements.md' './pkg/example.go'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS (test-traceability)"* ]]
}

@test "Fails numbered test tracing when requirements and tests are not 1:1 in both directions" {
  #R090-T03: 1:1 mismatch fixture reports both missing-in-tests and missing-in-requirements sections.
  #R090
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_numbered_traceability_mismatch_fixture "${fixture_root}"
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash "${fixture_root}/verify_requirements_traceability.sh" "${fixture_root}/requirements/fixture-requirements.md" "${fixture_root}/fixture.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Missing in tests (present in requirements)"* ]]
  [[ "$output" == *"R001-T04"* ]]
  [[ "$output" == *"Missing in requirements (present in tests)"* ]]
  [[ "$output" == *"R001-T03"* ]]
}

@test "Fails numbered test tracing when Tests bullets are malformed" {
  #R090-T04: Malformed tests bullet missing Rxxx-T## prefix triggers malformed-bullet failure output.
  #R090
  local fixture_root
  fixture_root="$(mktemp -d)"
  make_traceability_fixture "${fixture_root}" "scoped"
  cat > "${fixture_root}/requirements/fixture-requirements.md" <<'EOF'
# Fixture Requirements

## Scope

Applies to `fixture.sh`.

R001  Statement: First behavior.
Tests:
- Verify first behavior without numbered test ID.
EOF
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash "${fixture_root}/verify_requirements_traceability.sh" "${fixture_root}/requirements/fixture-requirements.md" "${fixture_root}/fixture.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"unnumbered/invalid test bullet"* ]]
  [[ "$output" == *"FAIL (requirements-numbered-tests)"* ]]
}

@test "Requirements-only mode skips numbered test 1:1 checks" {
  #R090-T05: Requirements-only doc skips the numbered-tag check.
  #R070
  #R090
  local fixture_root
  fixture_root="$(mktemp -d)"
  local HASH="#"
  mkdir -p "${fixture_root}/requirements" "${fixture_root}/testing/sh"
  cat > "${fixture_root}/requirements/phase-requirements.md" <<'EOF'
# Phase Requirements

## Scope

Requirements-only mode: true.

R001  Statement: Placeholder requirement while implementation is pending.
Tests:
- R001-T01: Placeholder numbered test entry while implementation is pending.
EOF
  cat > "${fixture_root}/testing/sh/phase.bats" <<EOF
#!/usr/bin/env bats
@test "placeholder" {
  ${HASH}R001-T99: Intentionally mismatched but should be skipped for requirements-only docs.
  [ 1 -eq 1 ]
}
EOF
  cp "${BATS_TEST_DIRNAME}/../../00_verify_requirements_traceability.sh" "${fixture_root}/verify_requirements_traceability.sh"
  run /bin/bash -c "cd '${fixture_root}' && /bin/bash './verify_requirements_traceability.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS (requirements-only)"* ]]
}
