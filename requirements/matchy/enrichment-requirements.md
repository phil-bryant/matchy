# Matchy Enrichment Requirements

## Scope

Applies to `matchy/enrichment.py`. Provides `EnrichmentMixin`, the candidate post-processing concern
extracted from the service orchestration module: Mailcart full-body enrichment and CLDR currency-token
filtering, run after retrieval and before ranking/AI selection. Mixed into `MatchService`.

R015  Statement: Enrich search candidates with the full Mailcart message body before scoring so amount, keyword, and compact-merchant hints can match against the real email body.
Design: `_enrich_candidate_bodies` fetches each candidate's full body via `MailcartClient.get_message(message_id)` and replaces the candidate's `body_text` with the upstream `text_body` (or `html_body` if no plain-text body) before ranking. Behavior is gated by `settings.mailcart_body_enrichment_enabled` and bounded by `settings.mailcart_body_enrichment_limit`. Duplicate message ids are fetched once; per-id Mailcart failures and empty bodies fall through to the original candidate so a flaky or missing message does not poison the whole run. Older Mailcart clients without `get_message` are no-ops.
Tests:
- R015-T01: Stub a `MailcartClient` whose `get_message` returns a body for one id and a 404 for another; verify the enriched candidate carries the new `body_text` while the un-enriched candidate retains its original preview-only `body_text`.
- R015-T02: Disable `mailcart_body_enrichment_enabled` via settings and verify candidates pass through unchanged (no `get_message` calls).

R050  Statement: Scope match candidates to emails containing a valid standalone CLDR currency code or symbol.
Design: After Mailcart body enrichment and before ranking/AI selection, candidates are filtered to messages whose subject, preview, or body contains a standalone CLDR currency code or symbol via the `MatchService`-held `CldrCurrenciesCache` matcher. Missing/malformed CLDR cache data yields an empty matcher and leaves candidates unfiltered so offline startup remains usable.
Tests:
- R050-T01: Verify a `$35.99` candidate remains while a no-currency candidate is removed before AI.
- R050-T02: Verify an empty CLDR matcher leaves candidates unfiltered.

R600  Statement: Build enrichment execution settings only when enrichment can run.
Design: `_body_enrichment_config` returns `None` unless candidates exist, enrichment is enabled, and
`mailcart_client.get_message` is callable; otherwise it returns bounded limit/timeout/worker configuration.
Tests:
- R600-T01: Disable enrichment and verify body enrichment short-circuits without any message fetch calls.

R605  Statement: Deduplicate candidate message IDs while preserving first-seen order.
Design: `_unique_message_ids` walks the configured enrichment prefix and appends each message id only on first sight.
Tests:
- R605-T01: Repeated candidate message IDs trigger only one Mailcart fetch while preserving output order.

R610  Statement: Fetch candidate payloads concurrently and tolerate per-message fetch failures.
Design: `_fetch_message_payloads` submits one future per message id, records successful payloads, logs and skips
per-future exceptions, and returns partial results when timeout occurs.
Tests:
- R610-T01: Enrichment continues when one message fetch fails and still applies successful payloads.

R615  Statement: Resolve enrichment body text from payload fields in deterministic precedence.
Design: `_enrichment_body_text` selects `text_body`, then `html_body`, then `body_text`, trimming whitespace and
falling back to the empty string for missing payloads.
Tests:
- R615-T01: Enrichment chooses available text/html fields in precedence order and preserves fallback behavior.

R620  Statement: Apply enriched payload rows to the configured candidate prefix only.
Design: `_apply_body_enrichment` rewrites candidates with resolved payload fields when body text is present and leaves
candidates unchanged when payloads are missing, extending untouched rows past `enrich_count`.
Tests:
- R620-T01: Enrichment rewrites available rows and preserves unresolved candidates unchanged.

## Changelog

- 2026-06-05: Extracted R015 (Mailcart body enrichment) and R050 (CLDR currency candidate filtering) from `service.py` into `enrichment.py`/`EnrichmentMixin`.
- 2026-06-06: Added R600-R620 helper requirements for enrichment configuration, deduped fetch dispatch, and payload application.
