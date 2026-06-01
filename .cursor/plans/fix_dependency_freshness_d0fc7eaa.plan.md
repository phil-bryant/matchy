---
name: Fix Dependency Freshness
overview: Fix `04_run_dependency_freshness_checks.sh` by bringing the direct Python dependency set up to date and then validating the freshness gate end-to-end. This keeps the script’s default failure behavior intact instead of suppressing or bypassing it.
todos:
  - id: move-workspace
    content: Move workspace to `/Users/phil/local/src/eggnest/matchy` after plan approval
    status: completed
  - id: update-requirements
    content: Pin stale and unpinned direct dependencies in `requirements.txt` to current PyPI versions
    status: completed
  - id: refresh-venv
    content: Refresh `matchy-venv` with the repository setup workflow
    status: completed
  - id: verify-freshness
    content: Run `04_run_dependency_freshness_checks.sh` and inspect generated reports
    status: completed
  - id: verify-tests
    content: Run unit tests and fix any compatibility issues from the dependency updates
    status: completed
isProject: false
---

# Fix Dependency Freshness Failure

## Diagnosis

`[04_run_dependency_freshness_checks.sh](/Users/phil/local/src/eggnest/matchy/04_run_dependency_freshness_checks.sh)` is intentionally strict: it runs the project venv’s `pip list --outdated --format=columns`, filters to direct entries from `[requirements.txt](/Users/phil/local/src/eggnest/matchy/requirements.txt)`, writes reports, and exits non-zero when any direct update is available by default.

A read-only PyPI check shows stale or non-deterministic direct requirements:

- `openai==2.38.0` -> `openai==2.40.0`
- `psycopg2-binary` is unpinned -> current `2.9.12`
- `pytest` is unpinned -> current `9.0.3`
- `mutmut` is unpinned -> current `3.5.0`
- `hypothesis==6.155.0` -> `hypothesis==6.155.1`
- `starlette==1.2.0` -> `starlette==1.2.1`

## Implementation Plan

1. Move the agent workspace to `/Users/phil/local/src/eggnest/matchy` before making project changes.
2. Update `[requirements.txt](/Users/phil/local/src/eggnest/matchy/requirements.txt)` to pin the stale/unpinned direct dependencies to the current PyPI versions above.
3. Rebuild or refresh the project venv using the repo’s normal workflow:
   - Use `[02_create_venv.sh](/Users/phil/local/src/eggnest/matchy/02_create_venv.sh)` only if `matchy-venv` is missing.
   - Run `[03_load_requirements.sh](/Users/phil/local/src/eggnest/matchy/03_load_requirements.sh)` with the correct venv active so installed packages match the updated requirements.
4. Run `[04_run_dependency_freshness_checks.sh](/Users/phil/local/src/eggnest/matchy/04_run_dependency_freshness_checks.sh)` normally and inspect `.security-reports/dependency-freshness.*` if it still fails.
5. Run focused validation for compatibility:
   - `[05_run_unit_tests.sh](/Users/phil/local/src/eggnest/matchy/05_run_unit_tests.sh)`
   - If needed, targeted tests around FastAPI/OpenAI/SQLAlchemy usage: `tests/py/test_api.py`, `tests/py/test_ai_ranker.py`, `tests/py/test_repository.py`.

## Guardrails

- Do not change `DEPENDENCY_FAIL_ON_UPDATES`, `DEPENDENCY_FAIL_ON_MAJOR`, or add environment overrides to make the check pass.
- Do not weaken `[04_run_dependency_freshness_checks.sh](/Users/phil/local/src/eggnest/matchy/04_run_dependency_freshness_checks.sh)` unless verification reveals a real parsing or reporting bug.
- If a latest package introduces an actual compatibility break, fix the app/test code against the new version rather than pinning stale versions to silence the freshness check.