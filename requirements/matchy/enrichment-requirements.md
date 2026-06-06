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

## Changelog

- 2026-06-05: Extracted R015 (Mailcart body enrichment) and R050 (CLDR currency candidate filtering) from `service.py` into `enrichment.py`/`EnrichmentMixin`.
