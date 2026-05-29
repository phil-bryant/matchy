---
name: Fix Bats warning hygiene
overview: Eliminate BW01/BW02 warnings by making Bats assertions explicit and version-safe while preserving existing test intent and lock-behavior coverage.
todos:
  - id: replace-run-negation
    content: Refactor BW02-triggering `run ! grep` assertions in mutation tests to a warning-free assertion pattern.
    status: completed
  - id: stabilize-lock-exit
    content: Make concurrent-lock rejection path return a deterministic non-zero exit code and assert that exact code in the Bats test.
    status: completed
  - id: validate-no-warnings
    content: Re-run unit test lane and confirm BW01/BW02 warnings are gone without regressions.
    status: completed
isProject: false
---

# Fix Bats Warning Sources

## What the warnings mean
- `BW02` is raised because `tests/sh/10_run_mutation_tests.bats` uses `run ! ...` (a `run` flag syntax) without declaring a minimum Bats version.
- `BW01` is raised because `tests/sh/12_run_all_checks_parallel.bats` runs a command that exits `127` while asserting only generic non-zero (`[ "$status" -ne 0 ]`), which Bats treats as potentially accidental `command not found`.

## Targeted implementation
- Update [`/Users/phil/local/src/matchy/tests/sh/10_run_mutation_tests.bats`](/Users/phil/local/src/matchy/tests/sh/10_run_mutation_tests.bats)
  - Replace the two `run ! grep -F ...` checks with `run grep -F ...` followed by explicit non-zero assertions.
  - Rationale: removes `BW02` without introducing version-floor coupling and matches the dominant assertion style already used in shell tests.

- Update [`/Users/phil/local/src/matchy/12_run_all_checks_parallel.sh`](/Users/phil/local/src/matchy/12_run_all_checks_parallel.sh)
  - Make lock-acquisition failure handling explicit/deterministic at call site (fail with expected code immediately when lock is active/unavailable).
  - Preserve current error message contract (`already active`) and lock cleanup behavior.

- Update [`/Users/phil/local/src/matchy/tests/sh/12_run_all_checks_parallel.bats`](/Users/phil/local/src/matchy/tests/sh/12_run_all_checks_parallel.bats)
  - Tighten the concurrent-run test to assert the exact expected lock-failure status (instead of generic non-zero), plus existing output substring check.
  - Rationale: prevents `BW01` and ensures the test validates intended lock semantics, not arbitrary failure.

## Verification
- Run `./05_run_unit_tests.sh`.
- Confirm:
  - all existing tests still pass,
  - no `BW01`/`BW02` warnings are emitted,
  - lock-contention test still validates both message and deterministic exit behavior.