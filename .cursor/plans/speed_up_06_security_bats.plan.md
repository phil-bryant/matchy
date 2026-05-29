---
name: speed up 06 security bats
overview: Speed up Matchy 06_run_security_checks bats from ~80-100s to under ~15s by valve-style stubs, file split, shared fixtures, detect-secrets foreground test mode, and removing 06 from the serial lane in 05_run_unit_tests.sh.
todos:
  - id: tier1-foreground-ds
    content: "Tier 1: add DETECT_SECRETS_USE_BACKGROUND_WAIT to 06_run_security_checks.sh; tests default foreground except R060-T01."
    status: completed
  - id: tier4-setup-file
    content: "Tier 4: setup_file_shared_fixture in tests/sh/helpers/common.bash; trash teardown."
    status: completed
  - id: tier2-stubs
    content: "Tier 2: tests/sh/helpers/security_stubs.bash with make_* stubs and setup_security_test."
    status: completed
  - id: tier3-split
    content: "Tier 3: split into 06_run_security_checks_{core,findings,detect_secrets}.bats."
    status: completed
  - id: tier6-parallel
    content: "Tier 6: drop ^06_ from serial lane in 05_run_unit_tests.sh + requirements."
    status: completed
  - id: tier7-reqs
    content: "Tier 7: update requirements/06 and 05 serial-lane docs."
    status: completed
  - id: verify-timing
    content: "Verify bats --timing on 06_* (~6.8s) and full 05 pass."
    status: completed
isProject: false
---

# Speed up Matchy 06_run_security_checks bats

See conversation plan for full tier breakdown, metrics, and verification checklist.
