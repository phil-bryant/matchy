# Matchy Settings Requirements

## Scope

Applies to `matchy/settings.py`.

R880  Statement: Resolve complete Teller DB configuration from 1psa during startup initialization.
Design: `__post_init__` invokes `_resolve_teller_db_config`, which prefers 1psa-backed values and populates host/user/password/port/database on the frozen settings object for runtime use.
Tests:
- R880-T01: Run with no Teller DB env vars and verify `Settings()` resolves DB fields from the default 1psa item.

R885  Statement: Support configurable 1psa item and `op://` references for DB resolution.
Design: `_resolve_db_config_from_1psa` plus `_build_1psa_db_field_refs`/`_parse_1psa_multi_output`/`_validate_1psa_secret_ref` resolve DB fields from item-name or `op://` references and parse supported 1psa response formats.
Tests:
- R885-T01: Stub item-name lookup and verify complete DB resolution through custom item reference.
- R885-T02: Stub `op://` lookup and verify complete DB resolution through `1psa read`.

R890  Statement: Use `~/.env` as the only DB fallback and fail clearly on invalid/incomplete config.
Design: If 1psa does not return complete DB fields, `_resolve_db_config_from_home_env` parses `~/.env`; `_coerce_db_config` enforces integer ports and required field presence, raising explicit runtime errors when unresolved.
Tests:
- R890-T01: Force 1psa DB lookup failure and verify fallback resolves from `~/.env`.
- R890-T02: Force both 1psa and `~/.env` failure and verify clear runtime error is raised.
- R890-T03: Provide non-integer port and verify validation failure is raised.

R895  Statement: Resolve optional Anthropic/OpenAI API keys with env precedence and tolerant 1psa fallback.
Design: `_resolve_optional_api_key` prefers env vars, then optional 1psa lookups (`_load_optional_secret_from_1psa`/`_build_1psa_command`) and keeps settings constructible when AI secrets are absent.
Tests:
- R895-T01: Stub Anthropic key lookup and verify value resolves from 1psa when env var is unset.
- R895-T02: Stub OpenAI key lookup and verify value resolves from 1psa when env var is unset.
- R895-T03: Set `ANTHROPIC_API_KEY` and verify env value overrides 1psa.
- R895-T04: Make AI-key 1psa lookups fail and verify settings still construct with empty keys.

R905  Statement: Expose Mailcart body enrichment feature flags with defaults and env overrides.
Design: `mailcart_body_enrichment_enabled` defaults to `true` and `mailcart_body_enrichment_limit` defaults to `75`, both overridable via `MATCHY_MAILCART_BODY_ENRICHMENT*` env vars.
Tests:
- R905-T01: Construct with no overrides and verify enabled flag + default limit.
- R905-T02: Set override env vars and verify flag/limit values are applied.

R910  Statement: Default Anthropic model to a stable pinned id while preserving env override behavior.
Design: `anthropic_model` falls back to `claude-sonnet-4-5` and accepts `MATCHY_ANTHROPIC_MODEL` override for controlled upgrades/rollbacks.
Tests:
- R910-T01: Construct with no model override and verify stable default model id.
- R910-T02: Set `MATCHY_ANTHROPIC_MODEL` and verify override is applied.

R915  Statement: Expose Mailcart transport timeout and CA bundle settings.
Design: `mailcart_search_timeout_seconds` provides configurable request timeout defaults and `mailcart_ca_bundle` exposes optional explicit certificate bundle path.
Tests:
- R915-T01: Verify default search timeout value when env var is unset.
- R915-T02: Verify search timeout env override is applied.
- R915-T03: Verify default CA bundle is empty.
- R915-T04: Verify CA bundle env override path is exposed.

R919  Statement: Expose CLDR currencies cache startup path/refresh controls.
Design: `cldr_currencies_cache_path`, `cldr_currencies_refresh_enabled`, and `cldr_currencies_refresh_timeout_seconds` default to local cache conventions and support env overrides.
Tests:
- R919-T01: Verify CLDR cache settings defaults and env overrides.

R882  Statement: Skip Postgres credential resolution when the teller DB profile targets sqlite.
Design: `__post_init__` resolves the active teller DB profile target via `_teller_profile_target()` (tolerant of missing teller/profile, preserving postgres-era behavior); for sqlite targets the `teller_db_*` resolution is skipped entirely because the repository binds to teller's profile-driven engine, which owns SQLCipher path/key resolution.
Tests:
- R882-T01: With a sqlite profile target, `Settings()` constructs without invoking `_resolve_teller_db_config`.

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
- 2026-05-24: Switched Teller DB resolution to 1psa-first full field config with `~/.env` fallback and explicit hard failure on unresolved config.
- 2026-05-29: Added R040 Mailcart search timeout and R045 explicit CA bundle settings.
- 2026-06-01: Added R050 CLDR currencies cache startup settings.
- 2026-06-06: Rebased settings traceability onto shard-1 ID band R880-R919 with anchored tests.
- 2026-06-12: Added R882 sqlite-profile credential skip; matchy now follows the teller DB profile chain (postgres or sqlite) through the repository engine.
