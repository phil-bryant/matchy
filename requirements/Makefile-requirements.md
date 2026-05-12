# Makefile Requirements

## Scope

Applies to `Makefile`.

R001  Statement: Expose discoverable top-level developer targets.
Design: `make help` lists concise descriptions for `build`, `test`, `run`, `sast`, `av`, and `clean`.
Tests:
- Run `make help` and verify those targets are listed.

R005  Statement: Keep build validation lightweight and deterministic.
Design: `make build` verifies the minimum required Matchy files (`pyproject.toml`, `matchy/api.py`) exist.
Tests:
- Run `make build` with required files present and verify success.
- Remove one required file in a fixture and verify failure.

R010  Statement: Route test execution through Matchy’s unit-test script.
Design: `make test` invokes `./04_run_unit_tests.sh`.
Tests:
- Run `make test` and verify the unit-test script is invoked.

R015  Statement: Route runtime execution through Matchy’s API launcher.
Design: `make run` invokes `./07_run_matchy_api.py`.
Tests:
- Run `make run` in a fixture and verify launcher invocation.

R020  Statement: Route security and antivirus lanes through dedicated scripts.
Design:
- `make sast` invokes `./05_run_security_checks.sh`
- `make av` invokes `./06_run_av_checks.sh`
Tests:
- Run `make sast` and `make av` with stubs and verify scripts are invoked.

R025  Statement: Keep orchestration aliases for common setup flows.
Design: Expose helper targets (`install-prerequisites`, `create-venv`, `load-requirements`, `unit-tests`, `security-checks`, `av-checks`, `verify-traceability`) that map to numbered scripts.
Tests:
- Invoke each helper target and verify the expected script is called.

R030  Statement: Provide safe idempotent cleanup.
Design: `make clean` removes/moves generated artifacts (`.security-reports`, caches, build/dist) without failing when already absent.
Tests:
- Create artifacts, run `make clean`, verify they are removed.
- Run `make clean` again and verify success.

## Changelog

- 2026-05-12: Reswizzled from legacy CMake/clang-tidy contract to Matchy script-driven workflow.
