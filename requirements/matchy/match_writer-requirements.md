# Matchy Match Writer Requirements

## Scope

Applies to `matchy/match_writer.py`. Provides `MatchWriterMixin`, the match-persistence query family
extracted from the repository module: candidate inserts, AI-result persistence, active-match conflict
handling, and human-confirmed inserts. Mixed into `MatchRepository` so its public method surface is
unchanged.

R680  Statement: Persist Mailcart metadata columns during candidate insertion.
Design: `insert_candidates` writes `cached_subject`, `cached_sender`, `cached_snippet`, and `cached_fetched_at` so downstream UIs can render candidate context without additional Mailcart lookups.
Tests:
- R680-T01: Verify candidate insert SQL includes cached metadata columns and values.

R685  Statement: Detect conflicting active matches before persisting selected AI candidates.
Design: `has_active_match` queries active rows by `email_message_id` and returns a boolean conflict signal used by AI result persistence.
Tests:
- R685-T01: Verify active-match query enforces `active = TRUE` and single-row existence checks.

R690  Statement: Persist AI outcomes with deterministic state transitions and run-status updates.
Design: `persist_ai_result` deactivates previous active rows, inserts no-match/selected/conflict rows with explanation JSON, and updates run status to `succeeded` or `needs_review`.
Tests:
- R690-T01: Verify persistence logic contains no-match/conflict handling and run-status update paths.

R695  Statement: Provide explicit deactivation of prior active rows before replacement writes.
Design: `deactivate_active_match` updates `transaction_email_match.active` to `FALSE` for a transaction in a single SQL statement.
Tests:
- R695-T01: Verify deactivate SQL updates active rows for the target transaction id.

R700  Statement: Persist human-confirmed selections with match id return value.
Design: `insert_human_confirmed_match` inserts `human_confirmed_ai_match` rows with optional note metadata and returns `match_id` for caller confirmation responses.
Tests:
- R700-T01: Verify human-confirm insert SQL uses `human_confirmed_ai_match` and returns `match_id`.

## Changelog

- 2026-06-05: Extracted R030 (cached candidate metadata on insert) plus the AI-result/human-confirm write methods from `repository.py` into `match_writer.py`/`MatchWriterMixin`.
- 2026-06-06: Rebased match-writer traceability onto shard-1 ID band R680-R700 with anchored tests.
- 2026-06-12: Made all writer SQL dual-target via `matchy/db_target.py`: jsonb casts collapse to plain text binds on SQLite, timestamps bind as ISO text on SQLite, and the human-confirm insert reads `last_insert_rowid()` on SQLite where the DBAPI cannot surface `INSERT..RETURNING` rows.
