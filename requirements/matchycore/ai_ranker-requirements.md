# Matchycore AI Ranker Requirements

## Scope

Applies to `src/core/include/matchycore/ai_ranker.hpp`, and `src/core/src/ai_ranker.cpp`.

R001  Statement: Maintain full first-party traceability coverage for this matchycore module.
Design: Scope files use scoped `#R001:` comments on implementations and parser-detected functions.
Tests:
- R001-T01: Run `bats tests/sh/ai_ranker.bats` and verify scoped `#R001:` tags exist for all scope paths.

## Changelog

- 2026-06-14: Added matchycore requirements coverage for traceability enforcement.
