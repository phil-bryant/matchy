---
name: Green Security And Traceability
overview: Fix the three failing checks by correcting traceability mismatches, removing true secret-pattern findings in tests, and repairing DAST TLS wiring so Schemathesis exercises real API behavior instead of startup misconfiguration errors.
todos:
  - id: fix-traceability-tags
    content: "Add missing #R050 source annotations and reconcile numbered requirement/test IDs for mailcart client."
    status: completed
  - id: remove-secret-literals
    content: Eliminate detect-secrets-triggering password literals from test_mailcart_client while preserving test behavior.
    status: completed
  - id: repair-dast-ca-bundle
    content: Update dast_app startup env wiring so Mailcart preflight verifies against mkcert root CA in DAST runs.
    status: completed
  - id: validate-all-failing-gates
    content: Run the three failing test scripts, then re-run full parallel checks to confirm everything is green.
    status: completed
isProject: false
---

# Make All Failing Gates Legitimately Green

## What is failing now
- `t04_run_requirements_traceability_tests.sh` fails on [`requirements/matchy/mailcart_client-requirements.md`](requirements/matchy/mailcart_client-requirements.md) because:
  - source file [`matchy/mailcart_client.py`](matchy/mailcart_client.py) is missing `#R050` scoped tags
  - numbered test IDs are out of sync between requirements and [`tests/py/test_mailcart_client.py`](tests/py/test_mailcart_client.py) (`R045-T02`, `R050-T01`, `R050-T02`, `R050-T03` mismatch)
- `t03_run_static_security_tests.sh` fails due to one detect-secrets `Secret Keyword` finding in [`tests/py/test_mailcart_client.py`](tests/py/test_mailcart_client.py) from inline `teller_db_password="pw"` literals.
- `t12_run_dynamic_security_tests.sh` fails because DAST startup sets `SSL_CERT_FILE` to the leaf localhost cert, causing Mailcart preflight TLS verification to fail and API endpoints to return 503 during Schemathesis runs.

## Implementation plan
1. **Repair traceability source mapping for R050**
   - Edit [`matchy/mailcart_client.py`](matchy/mailcart_client.py) to add explicit `#R050:` scoped comments on startup preflight transport behavior (`startup_preflight_healthcheck`, transport context helpers).
   - Keep behavior unchanged; this is traceability annotation alignment.

2. **Align numbered requirement/test IDs 1:1**
   - Update [`requirements/matchy/mailcart_client-requirements.md`](requirements/matchy/mailcart_client-requirements.md):
     - add missing `R045-T02` bullet for missing explicit CA bundle fail-fast behavior already tested
     - keep `R050-T01` as MatchService init preflight invocation
     - include separate bullets for preflight success-path transport config coverage and failure diagnostics coverage so IDs match actual tests
   - Update [`tests/py/test_mailcart_client.py`](tests/py/test_mailcart_client.py):
     - add/port an `R050-T01` test that verifies MatchService triggers preflight once during initialization
     - retag `R050` tests so `T01/T02/T03` map exactly to requirement bullets

3. **Remove real secret-pattern triggers in test code (no suppression)**
   - Edit [`tests/py/test_mailcart_client.py`](tests/py/test_mailcart_client.py) to remove unnecessary `teller_db_password="pw"` arguments from `Settings(...)`/`SimpleNamespace(...)` in mailcart-client unit tests.
   - Keep test intent unchanged by passing only fields required for each test.

4. **Fix DAST TLS trust wiring at app entrypoint**
   - Edit [`dast_app.py`](dast_app.py) so DAST startup sets `MATCHY_MAILCART_CA_BUNDLE` to the mkcert root CA when available (and when not already explicitly configured), ensuring `MailcartClient` uses a CA bundle appropriate for verifying the Mailcart HTTPS stub.
   - This preserves HTTPS verification while avoiding dependence on `SSL_CERT_FILE` leaf-cert behavior inherited from the security lane.

5. **Run targeted validation, then full parallel checks**
   - Run in order:
     - `./tests/t04_run_requirements_traceability_tests.sh`
     - `./tests/t03_run_static_security_tests.sh`
     - `./tests/t12_run_dynamic_security_tests.sh`
   - If all three pass, run `./04_run_all_checks_parallel.sh` for full confirmation.

## Success criteria
- Traceability check reports 16/16 passing with no missing `#R` tags and no numbered ID mismatch.
- SAST gate summary reports zero Medium+ blockers (detect-secrets finding removed without baseline/suppressions).
- Schemathesis run reports zero contract failures (no 503 misconfiguration responses during POST endpoint tests).
- Full parallel check run is green.