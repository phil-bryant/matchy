# Matchy Init Requirements

## Scope

Applies to `matchy/__init__.py`.

R001  Statement: Publish a stable package marker docstring in the module root.
Design: Keep `matchy.__init__` as a lightweight package marker with a non-empty top-level docstring.
Tests:
- R001-T01: Import `matchy` and verify `matchy.__doc__` is a non-empty string.

## Changelog

- 2026-05-18: Added package-init requirements coverage for repository traceability.
