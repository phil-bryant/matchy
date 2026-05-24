# Run Matchy API Requirements

## Scope

Applies to `08_run_matchy_api.py`.

R001  Statement: Provide an executable Python entrypoint for Matchy API startup.
Design: Script starts with a Python shebang and imports Matchy app factory.
Tests:
- R001-T01: Execute script in a fixture and verify it attempts to launch uvicorn.

R005  Statement: Launch API server with deterministic local bind settings.
Design: `uvicorn.run(create_app(), host="127.0.0.1", port=8790)` is used for local startup.
Tests:
- R005-T01: Stub uvicorn and verify host/port arguments are passed as expected.

R010  Statement: Startup profiling logs are opt-in via CLI flag.
Design: Profiling logs are disabled by default; passing `--profile` enables startup timing output for the launcher and app setup.
Tests:
- R010-T01: Run without `--profile` and verify startup profiling lines are absent.
- R010-T02: Run with `--profile` and verify startup profiling lines are emitted.

## Changelog

- 2026-05-12: Added requirements for `08_run_matchy_api.py` to satisfy numbered-script traceability coverage.
- 2026-05-24: Added opt-in `--profile` requirement for startup timing logs.
