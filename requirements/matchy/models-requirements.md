# Matchy Models Requirements

## Scope

Applies to `matchy/models.py`.

R001  Statement: Keep transaction and candidate model records immutable after construction.
Design: Use frozen dataclasses for model entities so attribute reassignment raises dataclass immutability errors.
Tests:
- R001-T01: Instantiate `TransactionInput` and verify field reassignment raises `FrozenInstanceError`.

R005  Statement: Provide per-instance default reason maps for ranked candidates.
Design: Use `field(default_factory=dict)` for `RankedCandidate.reasons` to avoid shared mutable defaults.
Tests:
- R005-T01: Create multiple `RankedCandidate` instances and verify reasons dictionaries are independent objects.

## Changelog

- 2026-05-18: Added models requirements coverage for immutability and default-reasons behavior.
