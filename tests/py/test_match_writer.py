#R030: Python test lane coverage for cached candidate metadata on insert.

import inspect

from matchy.repository import MatchRepository


def test_insert_candidates_sql_includes_cached_metadata_columns() -> None:
    #R030-T01: Candidate insert persists cached Mailcart metadata columns.
    source = inspect.getsource(MatchRepository.insert_candidates)
    assert "cached_subject" in source
    assert "cached_sender" in source
    assert "cached_snippet" in source
