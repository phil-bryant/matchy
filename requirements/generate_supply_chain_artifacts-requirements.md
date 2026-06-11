# Generate Supply Chain Artifacts Shim Requirements

## Scope

Applies to `src/scripts/security/generate_supply_chain_artifacts.py`.

R001  Statement: Shim resolves the runner-owned generator from the repo root.
Design: Compute repo root from `Path(__file__)` and derive `../runner/src/scripts/security/generate_supply_chain_artifacts.py`.
Tests:
- R001-T01: Verify shim source resolves repo root from `Path(__file__)` and references the runner generator path.

R005  Statement: Shim fails fast when the runner generator is missing.
Design: Validate `runner_script.is_file()` before execution and raise an explicit `Missing runner supply-chain generator` error when absent.
Tests:
- R005-T01: Verify shim source checks `runner_script.is_file()` and emits explicit missing-runner error text.

R010  Statement: Shim preserves CLI passthrough and executes the runner script as `__main__`.
Design: Rewrite `sys.argv` so the runner script path is argv[0], then invoke `runpy.run_path(..., run_name="__main__")`.
Tests:
- R010-T01: Verify shim source rewrites `sys.argv` and calls `runpy.run_path` with `run_name="__main__"`.
