# Matchy Service Requirements

## Scope

Applies to `matchy/service.py` (orchestration only). The responsibility clusters that previously
accreted into this module have been extracted to cohesive sibling modules, each with its own
requirements doc: scoped search/retrieval (search module, R005/R040), Mailcart body enrichment and
CLDR currency filtering (enrichment module, R015/R050), the Postgres-backed AI-skip cache (caching
module, R020), near-duplicate collapsing (near_duplicate module, R055), the optional email move
(email_move module, R060), and runtime profiling (runtime_profile module, R065). This module retains
only the api -> service -> repository orchestration.

R001  Statement: Fail early when transaction IDs are unknown.
Design: Raise `ValueError` when repository transaction lookup returns no row before candidate retrieval.
Tests:
- R001-T01: Stub repository transaction lookup to return none and verify `match_transaction` raises `ValueError`.

R010  Statement: Run pending unmatched transactions in batch using repository discovery.
Design: Load pending transaction ids from repository lookback query and invoke `match_transaction` for each id with requested trigger source.
Tests:
- R010-T01: Stub pending id discovery and verify `match_pending_transactions` delegates each id to `match_transaction`.

R025  Statement: `match_pending_transactions` tolerates per-transaction failures.
Design: A single transaction's exception (transient Anthropic 429, Mailcart blip, Graph error, etc.) MUST NOT abort the rest of the batch. Each entry in the returned list either reflects a real evaluation, a cache hit, or `{error: <message>, selected_message_ids: [], uncertain: True, ...}`. `mark_run_failed` has already recorded the per-row failure in the DB, so the next driver loop naturally retries that transaction.
Tests:
- R025-T01: Inject a `match_transaction` that raises on the second transaction and verify the batch still returns three entries (with the failing entry carrying `error`), and the third transaction was still processed.

R030  Statement: Pending batch matching should process transactions concurrently with deterministic output order.
Design: `match_pending_transactions` uses a bounded worker pool (`MATCHY_PENDING_MAX_WORKERS`, default `4`) to run per-transaction matches concurrently while preserving result row order and per-transaction failure tolerance.
Tests:
- R030-T01: Stub pending id discovery and verify `match_pending_transactions` invokes all discovered ids and returns deterministic ordered rows.

R045  Statement: Provide a human confirm path so the UI Confirm button can persist a human selection without triggering state transition conflicts on `teller.transaction_email_match`.
Design: `confirm_match` in MatchService deactivates any prior active match for the transaction then inserts a new row with state='human_confirmed_ai_match', selected_by='human', delegating to the repository's `deactivate_active_match` and `insert_human_confirmed_match`. Foreign-key violations on client-supplied ids surface as a domain `ValueError` (HTTP 404 at the API).
Tests:
- R045-T01: Verify `confirm_match` deactivates the prior active row, inserts the human-confirmed row, and returns the match_id (delegation test in test_service.py).


R300  Statement: `match_transactions_atomic` commits the shared repository unit-of-work exactly once for a fully-successful batch, threading one session into every per-transaction call with `record_failure=False`.
Design: `match_transactions_atomic` opens one shared repository session and passes it into each `match_transaction` call, committing only once at the end when all entries succeed.
Tests:
- R300-T01: Stub repository commit/rollback counters and verify one commit, zero rollbacks, shared session threading, and `record_failure=False` for each entry.

R305  Statement: `match_transactions_atomic` rolls back the shared session and re-raises when any per-transaction match raises.
Design: Any exception raised while processing an atomic batch bubbles out of the repository session context, forcing rollback semantics and preventing partial commits.
Tests:
- R305-T01: Inject a failing transaction in the batch and verify zero commits, one rollback, and propagated exception.

R310  Statement: `MatchService.__init__` runs the Mailcart startup preflight healthcheck exactly once when `mailcart_startup_healthcheck_enabled` is true.
Design: During initialization, service construction creates one Mailcart client and conditionally performs exactly one startup preflight check before request handling.
Tests:
- R310-T01: Build service with startup healthcheck enabled and stub collaborators to verify a single preflight invocation.

## Changelog

- 2026-05-18: Added service requirements coverage for missing transaction and query construction behavior.
- 2026-05-18: Added R010 pending batch-matching requirements for driver orchestration.
- 2026-05-19: Added R015 candidate-body enrichment, R020 Postgres-backed AI-skip cache, R025 per-transaction error tolerance.
- 2026-05-24: Added R030 concurrent pending-batch processing with configurable worker pool and deterministic result ordering.
- 2026-05-29: Added R040 scoped search tiering and R045 human confirm path.
- 2026-06-01: Added R050 CLDR currency-token candidate filtering before ranking and AI selection.
- 2026-06-04: Added R060 optional post-selection Mailcart move behavior gated by write+move flags.
- 2026-06-05: Decomposed the service god-module; R005/R015/R020/R040/R050/R055/R060 moved with their code to dedicated modules (search, enrichment, caching, near_duplicate, email_move). `service.py` now owns only R001/R010/R025/R030/R045 orchestration.
- 2026-06-06: Added R300/R305/R310 for atomic batch commit/rollback behavior and startup preflight-once orchestration.
