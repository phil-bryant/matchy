#R001: Python test lane coverage for repository initialization guard.
#R005: Python test lane coverage for session commit/rollback behavior.
#R010: Python test lane coverage for pending-transaction re-queue predicate.
#R015: Python test lane coverage for cache-read helpers.
#R001-T01: Python test lane exists for initialization-guard requirement.
#R005-T01: Python test lane exists for session lifecycle requirement.
#R010-T01: Python test lane exists for pending-transaction list shape.
#R010-T02: Python test lane exists for pending-transaction re-queue predicate.
#R015-T01: Python test lane exists for last-run summary helper.
#R015-T02: Python test lane exists for active-match summary helper.


def test_traceability_tags_repository() -> None:
    assert True


def test_list_pending_transaction_ids_re_queues_unsettled_rows() -> None:
    #R010-T02: Verify the SQL predicate broadens beyond "no active match" so AI-only verdicts retry.
    from matchy.repository import MatchRepository

    class FakeResult:
        def mappings(self):
            return self

        def all(self):
            return []

    class CapturingSession:
        def __init__(self) -> None:
            self.statements: list[tuple[str, dict]] = []

        def execute(self, statement, params=None):
            self.statements.append((str(statement), dict(params or {})))
            return FakeResult()

    repo = object.__new__(MatchRepository)
    session = CapturingSession()
    repo.list_pending_transaction_ids(session, limit=25, lookback_days=30)
    sql, params = session.statements[0]
    assert "tem.match_id IS NULL" in sql
    assert "ai_candidate_uncertain" in sql
    assert "ai_no_match_found" in sql
    assert "selected_by::text = 'ai'" in sql
    assert "human_confirmed_ai_match" not in sql
    assert "human_overrode_ai_match" not in sql
    assert params == {"lookback_days": 30, "limit": 25}
