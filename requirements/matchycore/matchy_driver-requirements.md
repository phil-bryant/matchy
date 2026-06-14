# Matchycore Matchy Driver Requirements

## Scope

Applies to `src/core/tools/matchy_driver.cpp`.

R001  Statement: Maintain full first-party traceability coverage for this matchycore module.
Design: Scope files use scoped `#R001:` comments on implementations and parser-detected functions.
Tests:
- R001-T01: Run `bats tests/sh/matchy_driver.bats` and verify scoped `#R001:` tags exist for all scope paths.

## Changelog

- 2026-06-14: Added matchycore requirements coverage for traceability enforcement.
