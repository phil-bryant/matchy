# Matchycore Repository Requirements

## Scope

Applies to `src/core/include/matchycore/repository.hpp`, `src/core/src/repository.cpp`, and `src/core/src/match_writer.cpp`.

R001  Statement: Maintain full first-party traceability coverage for this matchycore module.
Design: Scope files use scoped `#R001:` comments on implementations and parser-detected functions.
Tests:
- R001-T01: Run `bats tests/sh/repository.bats` and verify scoped `#R001:` tags exist for all scope paths.

## Changelog

- 2026-06-14: Added matchycore requirements coverage for traceability enforcement.
