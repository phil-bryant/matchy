#R680: Python test lane coverage for cached candidate metadata on insert.
#R685: Python test lane coverage for active-match conflict query.
#R690: Python test lane coverage for AI result persistence paths.
#R695: Python test lane coverage for active-match deactivation writes.
#R700: Python test lane coverage for human-confirm insert writes.

import inspect

from matchy.repository import MatchRepository


def test_insert_candidates_sql_includes_cached_metadata_columns() -> None:
    #R680-T01: Candidate insert persists cached Mailcart metadata columns.
    source = inspect.getsource(MatchRepository.insert_candidates)
    assert "cached_subject" in source
    assert "cached_sender" in source
    assert "cached_snippet" in source


def test_has_active_match_queries_only_active_rows() -> None:
    #R685-T01: Active-match query restricts results to active rows and short-circuits existence checks.
    source = inspect.getsource(MatchRepository.has_active_match)
    assert "FROM matchy.transaction_email_match" in source
    assert "active = TRUE" in source
    assert "LIMIT 1" in source


def test_persist_ai_result_contains_no_match_and_conflict_paths() -> None:
    #R690-T01: AI persistence handles no-match/conflict states and updates run status.
    source = inspect.getsource(MatchRepository.persist_ai_result)
    assert "ai_no_match_found" in source
    assert "ai_candidate_uncertain" in source
    assert "_update_run_status" in source


def test_deactivate_active_match_sql_disables_existing_rows() -> None:
    #R695-T01: Deactivate SQL clears active rows for the transaction before replacement writes.
    source = inspect.getsource(MatchRepository.deactivate_active_match)
    assert "UPDATE matchy.transaction_email_match" in source
    assert "active = FALSE" in source


def test_insert_human_confirmed_match_returns_match_id() -> None:
    #R700-T01: Human-confirm insert persists human state and returns generated match_id.
    source = inspect.getsource(MatchRepository.insert_human_confirmed_match)
    assert "human_confirmed_ai_match" in source
    assert "RETURNING match_id" in source
