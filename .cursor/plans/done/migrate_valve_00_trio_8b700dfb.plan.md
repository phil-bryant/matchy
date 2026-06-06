---
name: Migrate Valve 00 Trio
overview: Port valve’s mature `00_verify_requirements_traceability` requirements, script, and tests into matchy with full behavior parity, including advanced checks, while adapting repository layout conventions.
todos:
  - id: diff-valve-matchy-trio
    content: Compare valve and matchy trio files and record exact behavior gaps to port
    status: completed
  - id: port-requirements-doc
    content: Migrate valve requirements doc content and adapt all path references to matchy layout
    status: completed
  - id: port-verifier-script
    content: Migrate mature valve verifier logic with matchy path compatibility and preserve needed local exceptions
    status: completed
  - id: port-bats-suite
    content: Migrate valve Bats tests and adapt fixtures/assertions to testing/sh layout
    status: completed
  - id: run-and-fix-tests
    content: Execute Bats and repo traceability checks, then resolve parity or path regressions
    status: completed
isProject: false
---

# Migrate Valve 00 Trio Into Matchy

## Scope
Implement full parity migration of the `00_verify_requirements_traceability` trio from valve into matchy:
- Requirements spec
- Root verifier script
- Shell/Bats test suite

Target files:
- [requirements/00_verify_requirements_traceability-requirements.md](requirements/00_verify_requirements_traceability-requirements.md)
- [00_verify_requirements_traceability.sh](00_verify_requirements_traceability.sh)
- [testing/sh/00_verify_requirements_traceability.bats](testing/sh/00_verify_requirements_traceability.bats)

## Migration Approach
1. Replace matchy trio content with valve’s mature logic/spec/tests as the baseline.
2. Apply deterministic path/layout adaptation for matchy conventions:
- `tests/sh` -> `testing/sh`
- any test discovery patterns in script and requirements text updated to match matchy structure.
3. Preserve matchy-specific behavior only where required for compatibility (e.g., existing locked-file handling if still relevant after parity import).
4. Ensure advanced valve checks are included end-to-end:
- Go `_test.go` peer checks
- orphan software-file coverage
- requirements-test 1:1 mapping (R090 style)

## File-Level Work
- [requirements/00_verify_requirements_traceability-requirements.md](requirements/00_verify_requirements_traceability-requirements.md)
  - Import valve’s expanded requirement set and test clauses.
  - Update all repository-structure references to match matchy paths.
  - Keep requirement numbering and bullet semantics aligned with script behavior.

- [00_verify_requirements_traceability.sh](00_verify_requirements_traceability.sh)
  - Port mature validation flow from valve (full-run and single-pair modes).
  - Ensure discovery and verification logic points to matchy directories.
  - Retain strict-shell/security expectations and keep all checks traceable to requirements IDs.

- [testing/sh/00_verify_requirements_traceability.bats](testing/sh/00_verify_requirements_traceability.bats)
  - Port valve fixtures and assertions for advanced checks.
  - Rewrite fixture paths to match `testing/sh` conventions.
  - Keep test tags and IDs consistent with the migrated requirements doc.

## Validation Plan
- Run targeted verifier tests first:
  - `bats testing/sh/00_verify_requirements_traceability.bats`
- Run repo check entrypoint used by project shell checks (if present) to confirm no regression in traceability gating.
- Spot-check representative scenarios in fixtures:
  - pass/fail for scoped vs bundled tags
  - orphan file detection
  - Go peer test enforcement
  - requirements-test mapping validation

## Risks and Mitigations
- Path mismatch risk from valve (`tests/sh`) to matchy (`testing/sh`):
  - Mitigate by updating both script discovery logic and Bats fixture layouts together.
- Spec/implementation drift risk after import:
  - Mitigate by keeping requirements IDs synchronized with script checks and test tags in one pass.
- Potential conflict with existing matchy-only behavior:
  - Mitigate by reconciling intentionally after baseline import instead of mixing logic during copy.