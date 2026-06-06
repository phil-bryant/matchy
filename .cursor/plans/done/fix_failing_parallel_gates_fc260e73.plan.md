---
name: Fix failing parallel gates
overview: Resolve the two failing lanes by updating the actionable stale direct dependency and eliminating ShellCheck medium-level false positives in root pointer scripts, then re-verify the targeted gates.
todos:
  - id: bump-mutmut
    content: Update mutmut pin in requirements.in and regenerate requirements.txt lock + hashes
    status: completed
  - id: suppress-shellcheck-fp
    content: Add targeted SC2034 suppression above RUNBOOK_PROFILE in four root pointer scripts
    status: completed
  - id: reload-and-verify
    content: Reload requirements via 03_load_requirements.sh and rerun t02, t03, then full parallel suite
    status: completed
isProject: false
---

# Fix `t02` + `t03` Gate Failures

## Goal
Make the current failures in `t02_run_dependency_freshness_tests.sh` and `t03_run_static_security_tests.sh` pass without weakening gate policies.

## Confirmed root causes
- `t02` fails because `mutmut==3.5.0` is a direct pinned dependency and `3.6.0` is available (actionable outdated direct package).
- `t03` fails because ShellCheck reports 4x `SC2034` on `RUNBOOK_PROFILE="matchy"` in root pointer scripts; this is a false positive because `delegate_golden()` consumes `RUNBOOK_PROFILE` via sourced `pointer_shim.sh`.

## Implementation steps
1. Update direct dependency pin:
   - Edit [`/Users/phil/local/src/eggnest/matchy/requirements.in`](/Users/phil/local/src/eggnest/matchy/requirements.in):
     - `mutmut==3.5.0` -> `mutmut==3.6.0`
2. Regenerate lockfile from the source requirement file:
   - Rebuild [`/Users/phil/local/src/eggnest/matchy/requirements.txt`](/Users/phil/local/src/eggnest/matchy/requirements.txt) with `pip-compile --generate-hashes` so hashes and transitive locks stay consistent.
3. Fix SAST ShellCheck blockers in pointer scripts by adding a targeted suppression directly above `RUNBOOK_PROFILE`:
   - [`/Users/phil/local/src/eggnest/matchy/01_install_prerequisites.sh`](/Users/phil/local/src/eggnest/matchy/01_install_prerequisites.sh)
   - [`/Users/phil/local/src/eggnest/matchy/02_create_venv.sh`](/Users/phil/local/src/eggnest/matchy/02_create_venv.sh)
   - [`/Users/phil/local/src/eggnest/matchy/03_load_requirements.sh`](/Users/phil/local/src/eggnest/matchy/03_load_requirements.sh)
   - [`/Users/phil/local/src/eggnest/matchy/04_run_all_tests_parallel.sh`](/Users/phil/local/src/eggnest/matchy/04_run_all_tests_parallel.sh)
   - Insert:
     - `# shellcheck disable=SC2034  # consumed by pointer_shim.sh via delegate_golden()`
     - then keep `RUNBOOK_PROFILE="matchy"` unchanged.
4. Install refreshed dependencies using project workflow:
   - Run `activate` then run [`/Users/phil/local/src/eggnest/matchy/03_load_requirements.sh`](/Users/phil/local/src/eggnest/matchy/03_load_requirements.sh).
5. Validate only affected lanes first, then full run:
   - `./tests/t02_run_dependency_freshness_tests.sh`
   - `./tests/t03_run_static_security_tests.sh`
   - `./04_run_all_tests_parallel.sh` (final confidence check)

## Why this is the right fix
- It addresses the exact actionable stale pin causing `t02` failure.
- It removes only false-positive SAST blockers while preserving the existing pointer contract and delegation behavior.
- It keeps existing security gate strictness intact (no policy weakening, no severity reclassification).