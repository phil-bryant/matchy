# Matchy Caching Requirements

## Scope

Applies to `matchy/caching.py`. Provides `CachingMixin`, the Postgres-backed AI-skip cache concern
extracted from the service orchestration module: candidate-payload fingerprinting and the decision of
whether the prior AI verdict still applies. Mixed into `MatchService`.

R020  Statement: Skip the AI evaluation when nothing has changed since the previous run for the transaction.
Design: `match_transaction` computes a deterministic SHA-256 fingerprint of the rank-relevant candidate payload (`_candidate_set_hash`/`_candidate_message_id_hash`) and `_maybe_cached_response` short-circuits with `skipped=True` when (a) a prior run exists with a completed-evaluation status (`succeeded`, `needs_review`, `no_candidates`), (b) its `model_name` matches `AiRanker.planned_model_name()`, (c) its `prompt_version` equals `PROMPT_VERSION`, and (d) its candidate payload hashes to the same value as the current search. The skipped response echoes the active `transaction_email_match` row's `email_message_id`/`ai_confidence`/`state`. Failed runs are NOT cache-eligible so transient errors self-heal; an active `ai_no_match_found` state forces re-evaluation. The cache lives entirely in Postgres so restarts do not re-pay AI cost. `force_rematch` bypasses the cache.
Tests:
- R020-T01: Seed a prior `succeeded` run whose model+prompt+candidate set matches the current search and verify `match_transaction` returns `skipped=True`, no new `match_run` row is created, and the AI ranker is not invoked.
- R020-T02: Change the candidate id set and verify `match_transaction` proceeds to a full AI evaluation that creates a new `match_run` row.
- R020-T03: Seed a prior `failed` run and verify the cache check refuses the short-circuit so transient errors retry.

## Changelog

- 2026-06-05: Extracted R020 (Postgres-backed AI-skip cache and candidate fingerprinting) from `service.py` into `caching.py`/`CachingMixin`.
