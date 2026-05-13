# Matchy Settings Requirements

## Scope

Applies to `matchy/settings.py`.

R001  Statement: Resolve Teller DB password from 1psa by default.
Design: `Settings` uses `1psa -p localhost_postgres_teller` when no explicit 1psa reference override is provided.
Tests:
- Run with no Teller password env vars and verify `Settings().teller_db_password` resolves from default 1psa item.

R005  Statement: Resolve Teller DB password from configurable 1psa references.
Design: Resolve with `1psa`: use `1psa read <ref>` for `op://...` references and `1psa -p <item>` for item-name references.
Tests:
- Stub `1psa -p` to return a secret for item-name override references and verify `Settings().teller_db_password` uses that secret.
- Stub `1psa read` to return a secret for `op://...` references and verify `Settings().teller_db_password` uses that secret.

R010  Statement: Fail clearly when 1psa lookup cannot produce a usable password.
Design: Raise runtime errors when `1psa` is unavailable, returns non-zero, or returns an empty secret for the configured reference; include explicit service-account guidance when an invalid `OP_SERVICE_ACCOUNT_TOKEN` causes auth failure.
Tests:
- Stub `1psa` to fail and verify `Settings()` exits with non-zero and emits a clear error message.
- Resolve a 1psa item reference without `OP_SERVICE_ACCOUNT_TOKEN` and verify lookup still works for local-auth CLI sessions.

## Changelog

- 2026-05-13: Added 1psa-backed Teller DB password resolution requirements for `matchy/settings.py`.
- 2026-05-13: Added dual 1psa invocation support (`-p` item and `read op://`) for runtime compatibility.
- 2026-05-13: Added OP service-account token preflight and clearer auth-failure messaging.
- 2026-05-13: Removed mandatory token preflight; retain token-specific guidance only for explicit service-account auth failures.
- 2026-05-13: Switched Teller password strategy to 1psa-first default item resolution (`localhost_postgres_teller`).
