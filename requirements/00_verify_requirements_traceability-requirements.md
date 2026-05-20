# Verify Requirements Traceability Requirements

## Scope

Applies to `00_verify_requirements_traceability.sh` and requirement/test traceability policy in this repository.

R001  Statement: Run in strict shell mode with temporary working files.
Design: Use `umask 007`, `set -euo pipefail`, and `mktemp` files for set operations.
Tests:
- R001-T01: Verify script exits when required variables are unset.

R005  Statement: Discover and verify all `requirements/**/*-requirements.md` files by default.
Design: Enumerate requirement docs from the `requirements/` directory recursively and verify each discovered `*-requirements.md` doc in one run.
Tests:
- R005-T01: Run with no args and verify all discovered requirements documents are visited.

R010  Statement: Resolve source files referenced by each requirements document.
Design: Parse backticked source file paths from requirements scope/design text and verify each matching source file for that document.
Tests:
- R010-T01: Add a second source file reference to one requirements doc and verify both are checked.

R015  Statement: Fail clearly when discovered files or mappings are missing.
Design: For each requirements file, fail when no source files are discoverable or when a referenced source file does not exist unless requirements-only mode is explicitly declared.
Tests:
- R015-T01: Remove a referenced source file and verify explicit non-zero failure output.
- R015-T02: Provide a requirements file with no discoverable source mapping and verify explicit non-zero failure output.

R020  Statement: Parse requirement IDs from requirement-file start-of-line entries.
Design: Extract IDs matching `R###` with optional `-###` suffix and deduplicate.
Tests:
- R020-T01: Include duplicate IDs in requirements and verify deduped set behavior.

R025  Statement: Parse all `#R` tags from source content.
Design: Scan each line for one or many `#R###` tags with optional `-###` suffix.
Tests:
- R025-T01: Add multiple tags in one source line and verify each is extracted.

R030  Statement: Report missing and extra traceability IDs as set differences.
Design: Use `comm` comparisons against sorted unique ID sets.
Tests:
- R030-T01: Remove one source tag and verify it appears in missing list.
- R030-T02: Add unknown source tag and verify it appears in extra list.

R035  Statement: Exit success only when every enforceable traceability comparison matches.
Design: Return `0` only when all discovered requirements files and their source/test checks have no missing or extra IDs; otherwise return `1`.
Tests:
- R035-T01: Verify all discovered pairs matching returns pass.
- R035-T02: Verify any discovered mismatch returns non-zero.

R040  Statement: Enforce numbered script coverage by numbered requirements docs.
Design: During full-run mode, compare repository `NN_*.sh`/`NN_*.py` scripts against `requirements/NN_*-requirements.md` and fail when any numbered script lacks a matching numbered requirements document.
Tests:
- R040-T01: Add a numbered script without a matching numbered requirements doc and verify explicit failure output.
- R040-T02: Add matching numbered requirements doc and verify coverage pass output.

R045  Statement: Enforce numbered requirements scope alignment with numbered scripts.
Design: For each `requirements/NN_*-requirements.md`, require at least one numbered source reference in Scope that starts with the same `NN_` prefix.
Tests:
- R045-T01: Point a numbered requirements file to a differently numbered script and verify explicit mismatch failure.
- R045-T02: Point it back to matching `NN_` source and verify alignment pass output.

R050  Statement: Discover candidate test files for each requirements document.
Design: Infer test files from requirements path and scoped source conventions, including `tests/sh`, `tests/py`, and top-level `Makefile` mapping to `tests/sh/Makefile.bats`, while canonicalizing symlinked test paths. For Python sources, enforce presence of `tests/py/test_<source-stem>.py` and fail with explicit missing-lane output when absent.
Tests:
- R050-T01: Verify shell-script requirements discover matching `tests/sh/*.bats` candidates.
- R050-T02: Verify top-level `Makefile` requirements discover `tests/sh/Makefile.bats`.
- R050-T03: Verify python requirements discover `tests/py/test_*.py` candidates.
- R050-T04: Verify python requirements fail with explicit missing-lane output when `tests/py/test_<stem>.py` is absent.

R055  Statement: Parse `#R` tags from discovered test files.
Design: Reuse `#R###(-###)*` extraction to build deduplicated requirement-coverage ID sets from discovered tests.
Tests:
- R055-T01: Include multiple tags per test file line and verify extraction still captures all IDs.

R060  Statement: Enforce at least one tagged test per requirement ID for enforceable docs.
Design: For requirements docs with source mappings, fail when any requirement ID lacks tagged coverage from discovered tests.
Tests:
- R060-T01: Remove all tagged tests for one ID and verify explicit missing-ID failure output.
- R060-T02: Restore coverage and verify pass output.

R065  Statement: Reject anti-cheat header bundles and require scoped source comments.
Design: Fail when files use top-of-file bundled tags and require scoped traceability comments (`#R###:`) over implementation blocks.
Tests:
- R065-T01: Provide only bundled header tags and verify explicit anti-cheat failure.
- R065-T02: Provide unscoped tags and verify scoped-comment failure.
- R065-T03: Provide scoped comments and verify pass.

R070  Statement: Support explicit requirements-only mode for pre-implementation documents.
Design: If a requirements file declares `Requirements-only mode: true` in `## Scope`, skip source and test traceability checks for that file and report a pass-with-skip status.
Tests:
- R070-T01: Create a requirements-only doc with no source mappings and verify the verifier skips it successfully.
- R070-T02: Remove the requirements-only declaration and verify missing-source failure resumes.

R075  Statement: Enforce repository Go source-file peer `_test.go` coverage in full-run mode.
Design: During no-argument full-run mode, if `go.mod` exists, scan repository non-test `.go` files and fail when any source file lacks a same-directory peer `*_test.go` file with the same stem.
Tests:
- R075-T01: Run verifier in a Go-module fixture containing a package with `.go` files but no `_test.go` and verify explicit failure output.
- R075-T02: Add matching `_test.go` coverage and verify pass output.

R080  Statement: Discover Go package `_test.go` files for per-file requirements traceability.
Design: When requirements scope includes `.go` source files, discover all sibling package `*_test.go` files and include them in requirement-ID tagged test coverage checks.
Tests:
- R080-T01: Use a fixture requirements doc scoped to a Go source and verify sibling `*_test.go` files are discovered.
- R080-T02: Omit required `#R` tags from discovered Go tests and verify explicit missing tagged-test failure.

R085  Statement: Auto-detect repository software files that are not covered by any requirements document.
Design: During no-argument full-run mode, discover repository software sources (for example `.sh`, `.py`, non-test `.go`, `.sql`, and similar code files outside `requirements/` and `tests/`) and fail when any discovered file is not mapped from at least one `requirements/**/*-requirements.md` Scope source reference.
Tests:
- R085-T01: Add an unreferenced software file to a fixture repo and verify explicit full-run failure output naming the uncovered file.
- R085-T02: Add that file to a requirements Scope mapping and verify full-run coverage pass output.

R090  Statement: Enforce 1:1 numbered test-tag traceability (`Rxxx-T##` in requirements vs `#Rxxx-T##` in tests) for enforceable documents.
Design: Parse numbered test bullets under each requirements `Tests:` section and compare them as an exact set against discovered `#Rxxx-T##` tags in discovered tests, scoped to requirement IDs in that document. Fail when any numbered requirement test ID is missing in tests and when any numbered test tag exists in tests without a corresponding requirements numbered bullet. Also fail when `Tests:` bullets are malformed (for example, unnumbered bullets that should be `Rxxx-T##:`). This check runs alongside the existing `#R` coverage check (R060) and is skipped for requirements-only docs.
Tests:
- R090-T01: Provide a requirements numbered test ID with no matching `#Rxxx-T##` in tests and verify explicit "missing in tests" failure output.
- R090-T02: Provide a `#Rxxx-T##` in tests with no matching requirements numbered test bullet and verify explicit "missing in requirements" failure output.
- R090-T03: Provide both mismatch directions in one fixture and verify both failure sections are printed.
- R090-T04: Provide malformed `Tests:` bullets (missing `Rxxx-T##:` prefix) and verify explicit malformed-bullet failure output.
- R090-T05: Verify that a requirements-only doc skips the numbered-tag check.

## Changelog

- 2026-05-20: Renamed repository test directory from `testing/` to `tests/`.
- 2026-05-16: Strengthened R090 to require 1:1 numbered traceability between requirements `Rxxx-T##` bullets and discovered test `#Rxxx-T##` tags, including malformed-bullet rejection.

- 2026-05-09: Added Go package test discovery requirement for per-file Go traceability docs.
- 2026-05-10: Added repository-level auto-detection for software files that are missing requirements coverage.
- 2026-05-08: Reswizzled for Valve requirements-first workflow, added requirements-only mode, and removed stale UI-lane assumptions.
- 2026-05-07: Reswizzled discovery conventions for Piston (`Tests/sh` + SwiftPM `Tests/`) and removed email app-specific paths.
