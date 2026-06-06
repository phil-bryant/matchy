---
name: Runner mutation import fix
overview: Fix the shared Darwin mutation driver so mutant runs import mutated modules (not repo-root originals), then validate through runner and matchy mutation lanes.
todos:
  - id: driver-import-precedence
    content: Patch mutmut_darwin.py to enforce mutation-first module resolution during subprocess pytest runs.
    status: completed
  - id: runner-test-hardening
    content: Update mutmut_darwin.bats to assert the new execution/import behavior.
    status: completed
  - id: validate-runner-and-matchy
    content: Run runner shell tests and matchy t09 mutation lane; confirm real mutant kills and green gate.
    status: completed
isProject: false
---

# Fix Runner Mutation Import Precedence

## Goal
Ensure `mutmut` subprocess executions in `[runner/src/scripts/mutmut_darwin.py](runner/src/scripts/mutmut_darwin.py)` actually execute mutated code for flat-layout repos (for example `matchy/` at repo root), eliminating false `survived=all` outcomes.

## Planned Changes
- Update `[runner/src/scripts/mutmut_darwin.py](runner/src/scripts/mutmut_darwin.py)` to run mutant pytest subprocesses with a mutation-first import context so `matchy.scoring_core` resolves from `mutants` before repo root.
- Keep existing test-selection behavior (`tests_for_mutant` then full-suite escalation) while making import precedence deterministic for both `mutants/src` and legacy `mutants` layouts.
- Preserve existing environment setup (`MUTANT_UNDER_TEST`, venv `PATH`, `HYPOTHESIS_STORAGE_DIRECTORY`) and only change execution/import path mechanics.

## Validation Plan
- Extend runner coverage in `[runner/tests/sh/mutmut_darwin.bats](runner/tests/sh/mutmut_darwin.bats)` to assert the new mutation-first execution behavior (not only static prepare/execute markers).
- Run runner shell-unit lane to confirm no regression in helper behavior.
- Re-run `matchy` mutation lane via `[matchy/tests/t09_run_mutation_tests.sh](matchy/tests/t09_run_mutation_tests.sh)` and verify:
  - non-zero killed mutants for `matchy/scoring_core.py`
  - mutation score returns to expected passing range
  - `artifacts/mutation/mutation-summary.json` reflects real kill/survive distribution.

## Risk Notes
- Primary risk is breaking tests that implicitly depend on repo-root working directory; mitigation is to keep pytest `--rootdir` and absolute test paths unchanged while only fixing import precedence.
- This is a shared-runner change, so impact extends to all repos using the Darwin mutation driver; runner tests and one real consumer (`matchy`) will be used as acceptance gates before completion.