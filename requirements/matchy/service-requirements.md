# Matchy Service Requirements

## Scope

Applies to `matchy/service.py`.

R001  Statement: Fail early when transaction IDs are unknown.
Design: Raise `ValueError` when repository transaction lookup returns no row before candidate retrieval.
Tests:
- R001-T01: Stub repository transaction lookup to return none and verify `match_transaction` raises `ValueError`.

R005  Statement: Build deterministic normalized search queries from transaction text.
Design: Normalize description/counterparty text to lowercase alphanumeric tokens, drop short/numeric tokens, and select deterministic token subsets.
Tests:
- R005-T01: Call `_build_query` and `_build_broad_query` with noisy text and verify normalized deterministic outputs.

R010  Statement: Run pending unmatched transactions in batch using repository discovery.
Design: Load pending transaction ids from repository lookback query and invoke `match_transaction` for each id with requested trigger source.
Tests:
- R010-T01: Stub pending id discovery and verify `match_pending_transactions` delegates each id to `match_transaction`.

R025  Statement: `match_pending_transactions` tolerates per-transaction failures.
Design: A single transaction's exception (transient Anthropic 429, Mailcart blip, Graph error, etc.) MUST NOT abort the rest of the batch. Each entry in the returned list either reflects a real evaluation, a cache hit, or `{error: <message>, selected_message_ids: [], uncertain: True, ...}`. `mark_run_failed` has already recorded the per-row failure in the DB, so the next driver loop naturally retries that transaction.
Tests:
- R025-T01: Inject a `match_transaction` that raises on the second transaction and verify the batch still returns three entries (with the failing entry carrying `error`), and the third transaction was still processed.

R020  Statement: Skip the AI evaluation when nothing has changed since the previous run for the transaction.
Design: `match_transaction` runs the Mailcart search up-front (before creating a new `match_run` row) and computes a deterministic SHA-256 fingerprint of the candidate id set. It then queries `read_last_run_summary` for the most recent `match_run`, and short-circuits with `skipped=True` when (a) the last run's `status` is a completed AI evaluation (`succeeded`, `needs_review`, or `no_candidates`), (b) its `model_name` matches `AiRanker.planned_model_name()`, (c) its `prompt_version` equals `PROMPT_VERSION`, and (d) its candidate id set hashes to the same value as the current search. The skipped response echoes the active `transaction_email_match` row's `email_message_id`/`ai_confidence`/`state` so callers get parity with a fresh evaluation. Failed runs are NOT cache-eligible so transient Mailcart/Anthropic errors self-heal on the next loop. The cache lives entirely in Postgres so taking matchy up and down does not re-pay AI cost.
Tests:
- R020-T01: Seed a prior `succeeded` run whose model+prompt+candidate id set matches the current search and verify `match_transaction` returns `skipped=True`, no new `match_run` row is created, and the AI ranker is not invoked.
- R020-T02: Change one candidate id (or change the model/prompt) and verify `match_transaction` proceeds to a full AI evaluation that creates a new `match_run` row.
- R020-T03: Seed a prior `failed` run and verify the cache check refuses the short-circuit so transient errors retry.

R015  Statement: Enrich search candidates with the full Mailcart message body before scoring so amount, keyword, and compact-merchant hints can match against the real email body.
Design: `_enrich_candidate_bodies` iterates the candidate list returned from any `search_candidates(...)` call, fetches each candidate's full body via `MailcartClient.get_message(message_id)`, and replaces the candidate's `body_text` with the upstream `text_body` (or `html_body` if no plain-text body) before invoking `rank_candidates`. Behavior is gated by `settings.mailcart_body_enrichment_enabled` (default `True`) and bounded by `settings.mailcart_body_enrichment_limit` (default `75`). Per-id Mailcart failures and empty bodies fall through to the original candidate so a flaky or missing message does not poison the whole run. Older Mailcart clients without `get_message` are no-ops.
Tests:
- R015-T01: Stub a `MailcartClient` whose `get_message` returns a body for one id and a 404 for another; verify the enriched candidate carries the new `body_text` while the un-enriched candidate retains its original preview-only `body_text`.
- R015-T02: Disable `mailcart_body_enrichment_enabled` via settings and verify candidates pass through unchanged (no `get_message` calls).

R030  Statement: Pending batch matching should process transactions concurrently with deterministic output order.
Design: `match_pending_transactions` uses a bounded worker pool (`MATCHY_PENDING_MAX_WORKERS`, default `4`) to run per-transaction matches concurrently while preserving result row order and per-transaction failure tolerance.
Tests:
- R030-T01: Stub pending id discovery and verify `match_pending_transactions` invokes all discovered ids and returns deterministic ordered rows.

R040  Statement: Execute the scoped retrieval fallback chain (terms+date → terms-only → broad-term → empty) without yet creating a match_run row.
Design: `_search_candidates` intentionally uses scoped Mailcart syntax (`subject:`/`body:` plus optional `from:`/`to:` date bounds) and unions results across terms to improve recall while preserving deterministic ordering. Each mailcart search is a ~15-20s full-mailbox Graph scan; the driver already runs several transactions in parallel, so per-transaction load must be kept to ~one scan. Queries are issued one at a time and stop at the first that returns anything (early-stop). Body matching leads because the merchant name reliably appears in receipt/confirmation bodies. Subject, a window-free retry, and the historical recency fallback only run when earlier queries come back empty. Results are de-duplicated by message_id while preserving order.
Tests:
- R040-T01: Verify early-stop behavior returns on first successful tier and subsequent tiers are not invoked.
- R040-T02: Verify result de-duplication preserves deterministic order.

R045  Statement: Provide a human confirm endpoint so the UI Confirm button can persist a human selection without triggering state transition conflicts on `teller.transaction_email_match`.
Design: `confirm_match` in MatchService deactivates any prior active match for the transaction then inserts a new row with state='human_confirmed_ai_match', selected_by='human'. The repository exposes `deactivate_active_match` and `insert_human_confirmed_match`. The API exposes POST /v1/matchy/confirm accepting transaction_id, email_message_id, optional note.
Tests:
- R045-T01: Python test lane exists for human confirm requirement (delegation test in test_api.py).

R050  Statement: Scope match candidates to emails containing a valid standalone CLDR currency code or symbol.
Design: `MatchService` loads a `CldrCurrenciesCache` matcher once at initialization. After Mailcart body
enrichment and before ranking/AI selection, candidates are filtered to messages whose subject, preview,
or body contains a standalone CLDR currency code or symbol. Missing/malformed CLDR cache data yields an
empty matcher and leaves candidates unfiltered so offline startup remains usable. Because `TransactionInput`
has no currency field, the filter accepts any valid CLDR currency token rather than a transaction-specific
currency.
Tests:
- R050-T01: Verify a `$35.99` candidate remains while a no-currency candidate is removed before AI.
- R050-T02: Verify an empty CLDR matcher leaves candidates unfiltered.

R055  Statement: Collapse near-duplicate candidate emails (forwarded or marketing variants of the same receipt) using SimHash fingerprints under a Hamming-distance threshold.
Design: `_simhash64` builds a 64-bit fingerprint from a candidate's long tokens using keyed BLAKE2b per-bit voting; `_hamming_distance` counts differing bits. `_collapse_near_duplicates` keeps the first representative of each cluster, never collapses contentless (zero) fingerprints, and is a no-op for a non-positive threshold or trivial input. `_near_duplicate_max_distance` resolves the threshold from `near_duplicate_max_hamming_distance`, defaulting to 0 (disabled) and rejecting non-positive/invalid values. Collapsing runs in `match_transaction` after body enrichment so similarity is judged on full bodies.
Tests:
- R055-T01: SimHash is deterministic, zero for empty text, and far in Hamming distance for unrelated text (`tests/py/test_service.py`).
- R055-T02: Hamming distance counts differing bits and is zero for equal fingerprints (`tests/py/test_service.py`).
- R055-T03: Identical bodies collapse to the first representative, distinct content survives, and disabled/trivial input is unchanged (`tests/py/test_service.py`).
- R055-T04: The distance resolver defaults to disabled, honors positive values, and rejects invalid input (`tests/py/test_service.py`).

## Changelog

- 2026-05-18: Added service requirements coverage for missing transaction and query construction behavior.
- 2026-05-18: Added R010 pending batch-matching requirements for driver orchestration.
- 2026-05-19: Added R015 candidate-body enrichment so scoring can disambiguate same-day same-merchant transactions whose fare appears only in the email body (Lyft, Uber, food delivery, etc.).
- 2026-05-19: Added R020 Postgres-backed cache so matchy skips redundant AI evaluations when the candidate id set and model+prompt are unchanged since the previous run, keeping the auto-driver's per-loop cost bounded to a single Mailcart search.
- 2026-05-19: Added R025 per-transaction error tolerance in `match_pending_transactions` so a single 429/blip does not abort the whole batch.
- 2026-05-24: Added R030 concurrent pending-batch processing with configurable worker pool and deterministic result ordering.
- 2026-05-29: Added R040 scoped search tiering with early-stop and deterministic de-duplication.
- 2026-05-29: Added R045 human confirm endpoint so UI Confirm button can persist human selection without state transition conflicts.
- 2026-06-01: Added R050 CLDR currency-token candidate filtering before ranking and AI selection.
