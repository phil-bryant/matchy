# Matchy Settings Requirements

## Scope

Applies to `matchy/settings.py`.

R001  Statement: Resolve Teller DB password from 1psa by default.
Design: `Settings` uses `1psa -p localhost_postgres_teller` when no explicit 1psa reference override is provided.
Tests:
- R001-T01: Run with no Teller password env vars and verify `Settings().teller_db_password` resolves from default 1psa item.

R005  Statement: Resolve Teller DB password from configurable 1psa references.
Design: Resolve with `1psa`: use `1psa read <ref>` for `op://...` references and `1psa -p <item>` for item-name references.
Tests:
- R005-T01: Stub `1psa -p` to return a secret for item-name override references and verify `Settings().teller_db_password` uses that secret.
- R005-T02: Stub `1psa read` to return a secret for `op://...` references and verify `Settings().teller_db_password` uses that secret.

R010  Statement: Fail clearly when 1psa lookup cannot produce a usable password.
Design: Raise runtime errors when `1psa` is unavailable, returns non-zero, or returns an empty secret for the configured reference; include explicit service-account guidance when an invalid `OP_SERVICE_ACCOUNT_TOKEN` causes auth failure.
Tests:
- R010-T01: Stub `1psa` to fail and verify `Settings()` exits with non-zero and emits a clear error message.
- R010-T02: Stub `1psa` to emit a service-account auth-failure pattern with `OP_SERVICE_ACCOUNT_TOKEN` set and verify `Settings()` raises the targeted auth guidance error.

R015  Statement: Resolve AI API keys from 1psa with Anthropic primary and OpenAI fallback.
Design: `Settings` resolves `anthropic_api_key` from 1psa item `anthropic_api_key` (override `MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM`) and `openai_api_key` from 1psa item `openai_api_key` (override `MATCHY_OPENAI_API_KEY_1PSA_ITEM`); env vars `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` take precedence; missing 1psa items or `1psa` failures resolve to empty strings so the deterministic fallback can run.
Rationale: Matchy prefers Claude for transaction↔email matching but must keep running when either key is absent so the API stays usable in offline/local contexts.
Tests:
- R015-T01: Stub `1psa -p anthropic_api_key` to return a secret and verify `Settings().anthropic_api_key` resolves from 1psa when env var is unset.
- R015-T02: Stub `1psa -p openai_api_key` to return a secret and verify `Settings().openai_api_key` resolves from 1psa when env var is unset.
- R015-T03: Set `ANTHROPIC_API_KEY` env var and verify it overrides any 1psa value for the anthropic key.
- R015-T04: Stub `1psa` to fail for AI items and verify `Settings()` still constructs with empty AI keys.

R035  Statement: Default the Anthropic model to a stable dated id (not the deprecated `-latest` aliases).
Design: `Settings.anthropic_model` reads `MATCHY_ANTHROPIC_MODEL` and falls back to `claude-sonnet-4-5`. Anthropic deprecated and now 404s requests against the `-latest` aliases (e.g., `claude-3-5-sonnet-latest`), so the default must be a dated/stable model id. Callers retain the env override for upgrades and rollbacks.
Tests:
- R035-T01: Construct `Settings` with no env override and verify `anthropic_model == "claude-sonnet-4-5"`.
- R035-T02: Set `MATCHY_ANTHROPIC_MODEL=claude-opus-x` and verify `Settings().anthropic_model == "claude-opus-x"`.

R030  Statement: Expose feature flags for Mailcart body enrichment used by the matching service.
Design: `Settings` reads `MATCHY_MAILCART_BODY_ENRICHMENT` (default `true`) into the boolean `mailcart_body_enrichment_enabled` and `MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT` (default `75`) into the integer `mailcart_body_enrichment_limit`, which control whether and how many candidates `MatchService` enriches with the full email body before scoring.
Tests:
- R030-T01: Construct `Settings` with no env overrides and verify `mailcart_body_enrichment_enabled is True` and `mailcart_body_enrichment_limit == 75`.
- R030-T02: Set `MATCHY_MAILCART_BODY_ENRICHMENT=false` and `MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT=10`, construct `Settings`, and verify the flag is `False` and the limit is `10`.

## Changelog

- 2026-05-13: Added 1psa-backed Teller DB password resolution requirements for `matchy/settings.py`.
- 2026-05-13: Added dual 1psa invocation support (`-p` item and `read op://`) for runtime compatibility.
- 2026-05-13: Added OP service-account token preflight and clearer auth-failure messaging.
- 2026-05-13: Removed mandatory token preflight; retain token-specific guidance only for explicit service-account auth failures.
- 2026-05-13: Switched Teller password strategy to 1psa-first default item resolution (`localhost_postgres_teller`).
- 2026-05-18: Added R015: Anthropic-primary / OpenAI-fallback AI key resolution from 1psa with env-var overrides and tolerant missing items.
- 2026-05-18: Reformatted Tests bullets with `Rxxx-Tyy:` prefixes per new traceability check.
- 2026-05-19: Added R030 Mailcart body-enrichment feature flags (`mailcart_body_enrichment_enabled`, `mailcart_body_enrichment_limit`).
- 2026-05-19: Added R035 pinning the default Anthropic model to `claude-sonnet-4-5` since the `-latest` alias was deprecated and now 404s.
