# Matchycore API Contract Requirements

## Scope

Applies to `src/core/include/matchycore/api_contract.hpp`.

R001  Statement: Maintain full first-party traceability coverage for this matchycore module.
Design: Scope files use scoped `#R001:` comments on implementations and parser-detected functions.
Tests:
- R001-T01: Run `bats tests/sh/api_contract.bats` and verify scoped `#R001:` tags exist for all scope paths.

## Changelog

- 2026-06-14: Added matchycore requirements coverage for the extracted request-validation and error-mapping contract.
