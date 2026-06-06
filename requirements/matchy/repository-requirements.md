# Matchy Repository Requirements

## Scope

Applies to `matchy/repository.py` (engine/session lifecycle, transaction load, run lifecycle, pending
discovery, and the cache-read summaries). The match-persistence query family (candidate inserts,
AI-result persistence, human confirm) was extracted to the match_writer module (R030) and mixed back
into `MatchRepository`, so the repository's public method surface is unchanged.

R001  Statement: Require Teller DB password before repository initialization.
Design: Reject initialization when `teller_db_password` is empty to prevent anonymous write attempts.
Tests:
- R001-T01: Initialize repository with empty password and verify runtime error.

R005  Statement: Commit successful sessions and rollback failed sessions.
Design: Session context manager commits after successful work, rolls back on exceptions, and always closes the session.
Tests:
- R005-T01: Use a fake session factory and verify commit on success and rollback on failure.

R015  Statement: Expose the most recent match run summary (run + candidate id set) and the active match row for cache-hit short-circuiting in the service layer.
Design: `read_last_run_summary(transaction_id)` returns `{match_run_id, status, model_name, prompt_version, candidate_message_ids}` for the newest `transaction_email_match_run` row for the transaction or `None` when no runs exist. `read_active_match_summary(transaction_id)` returns the active `transaction_email_match` row's `{match_id, email_message_id, state, ai_confidence, selected_by}` or `None`. Together they let `MatchService.match_transaction` decide whether the current search result is identical to the previous evaluation (same candidate id set + same model + same prompt version) and therefore whether the AI call can be skipped. Cache state is persisted in Postgres (no in-process cache) so matchy can be restarted freely without re-paying AI cost.
Tests:
- R015-T01: Seed run + candidate rows and verify `read_last_run_summary` returns the latest run's status/model/prompt + the candidate id set, and returns `None` when the transaction has no runs.
- R015-T02: Seed an active match row and verify `read_active_match_summary` returns the matching dict, and returns `None` when no active row exists.

R010  Statement: Discover pending transaction ids for any transaction whose active match is not in a settled state.
Design: Query `teller.transaction` left-joined with `teller.transaction_email_match` (`active = TRUE`) and latest run metadata, then return ids where the active match row is missing, `state = 'ai_candidate_uncertain'`, or (`state = 'ai_no_match_found' AND selected_by = 'ai'`). Transactions inside the configurable lookback window are eligible, and transactions with no prior `transaction_email_match_run` row are also eligible regardless of date so teller-visible never-processed rows eventually get their first run. Settled transactions — high-confidence AI matches (`ai_match_confident`), human-confirmed matches (`human_confirmed_ai_match`), human overrides (`human_overrode_ai_match`), and human-marked no-email (`ai_no_match_found` with `selected_by = 'human'`) — are excluded so matchy never re-runs against a human-authoritative decision. Results are sorted deterministically by `date DESC, transaction_id ASC`.
Tests:
- R010-T01: Stub SQL execution rows and verify `list_pending_transaction_ids` returns the discovered transaction ids.
- R010-T02: Verify the SQL predicate includes both the `ai_candidate_uncertain` re-queue clause and the `ai_no_match_found`+`selected_by='ai'` re-queue clause so AI-only verdicts are retried while human-authoritative rows are not.

R720  Statement: Map loaded transaction rows into normalized TransactionInput values.
Design: `load_transaction` reads teller transaction/counterparty fields, converts amount to Decimal, attaches UTC to
timestamp, and returns `None` when no transaction exists.
Tests:
- R720-T01: Return mapped TransactionInput values for a row and `None` for missing transaction ids.

R721  Statement: Create needs-review match runs and return generated run identifiers.
Design: `create_run` inserts a `transaction_email_match_run` row with provided trigger/model/prompt values and
initial `needs_review` status, returning `match_run_id`.
Tests:
- R721-T01: Verify inserted run returns generated run id with expected SQL parameters.

R722  Statement: Update run model metadata independently of run status fields.
Design: `update_run_model_name` executes a targeted update that sets `model_name` for the requested run id only.
Tests:
- R722-T01: Verify model-name update SQL and parameters target only the selected run.

R723  Statement: Enumerate active email ids tied to other transactions.
Design: `list_active_email_ids_for_other_transactions` queries active non-null email ids excluding the current
transaction id and returns a deduplicated string set.
Tests:
- R723-T01: Verify active-other-transaction email ids are returned as a deduplicated set.

R724  Statement: Persist run completion status updates with optional error text.
Design: `_update_run_status` writes status/error_text and stamps `completed_at` for the selected run id.
Tests:
- R724-T01: Verify status update writes completion timestamp and propagated error text.

R725  Statement: Mark failed runs through a single delegated status-update path.
Design: `mark_run_failed` delegates to `_update_run_status` with status `failed` and caller-provided error text.
Tests:
- R725-T01: Verify failed-run helper delegates to `_update_run_status` with expected arguments.

## Changelog

- 2026-05-18: Added repository requirements for initialization guard and session lifecycle.
- 2026-05-18: Added R010 pending transaction discovery requirements for batch match drivers.
- 2026-05-19: Broadened R010 to re-queue `ai_candidate_uncertain` and AI-only `ai_no_match_found` rows so transient Mailcart/Graph failures self-heal on subsequent matchy runs while human-authoritative states (`human_confirmed_ai_match`, `human_overrode_ai_match`, human-marked `ai_no_match_found`) remain sticky.
- 2026-05-19: Added R015 cache-read helpers so the service layer can short-circuit redundant AI evaluations using the already-persisted match_run + candidate state.
- 2026-05-27: Expanded R010 so transactions with no prior match_run are eligible regardless of lookback window, ensuring teller-visible never-run rows are backfilled.
- 2026-06-05: Extracted R030 (cached candidate metadata on insert) and the AI-result/human-confirm write methods to `matchy/match_writer.py`; `repository.py` retains R001/R005/R010/R015.
- 2026-06-06: Added R720-R725 repository helper requirements for transaction loading, run lifecycle writes, and active-id exclusion queries.
