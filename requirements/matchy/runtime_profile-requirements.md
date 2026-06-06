# Matchy Runtime Profile Requirements

## Scope

Applies to `matchy/runtime_profile.py`. Provides the cross-cutting runtime-profiling instrumentation
(`_runtime_profile_enabled`, `_runtime_profile_log`) extracted from the service orchestration module so
both the orchestration and scoped search concerns emit consistent, opt-in timing breadcrumbs.

R065  Statement: Gate verbose runtime profiling breadcrumbs behind an environment flag.
Design: `_runtime_profile_enabled` reads `MATCHY_RUNTIME_PROFILE` (default off). `_runtime_profile_log` prints a single `[matchy-runtime] <phase> | <details>` line to stdout only when profiling is enabled, so normal (unset) runs stay silent and the auto-driver can turn on per-phase timing on demand.
Tests:
- R065-T01: Verify profiling is disabled by default (no output) and emits a breadcrumb only when `MATCHY_RUNTIME_PROFILE=true`.

## Changelog

- 2026-06-05: Extracted R065 (gated runtime-profiling instrumentation) from `service.py` into `runtime_profile.py`.
