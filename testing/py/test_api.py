#R001: Python test lane coverage for health endpoint behavior.
#R005: Python test lane coverage for missing-transaction HTTP mapping.
#R010: Python test lane coverage for pending-run endpoint delegation.
#R001-T01: Python test lane exists for health endpoint requirement.
#R005-T01: Python test lane exists for 404 mapping requirement.
#R010-T01: Python test lane exists for pending-run endpoint requirement.

from fastapi.testclient import TestClient

import matchy.api as api
from matchy.api import create_app


def test_api_health_endpoint_returns_status_ok() -> None:
    #R001: Health endpoint returns deterministic status payload.
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_api_run_endpoint_maps_unknown_transaction_to_http_404() -> None:
    #R005: ValueError from service is converted into HTTP 404.
    class StubService:
        def match_transaction(self, transaction_id, trigger_source="manual"):
            raise ValueError("Unknown transaction_id: missing")

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/runs",
            json={"transaction_ids": ["missing"], "trigger_source": "manual"},
        )
        assert response.status_code == 404
    finally:
        api.MatchService = old


def test_api_pending_run_endpoint_delegates_to_service_batch_matcher() -> None:
    #R010: Pending-run endpoint delegates to service batch matching with validated request fields.
    class StubService:
        def match_pending_transactions(self, limit=100, lookback_days=14, trigger_source="auto"):
            return [{"ok": True, "limit": limit, "lookback_days": lookback_days, "trigger_source": trigger_source}]

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/runs/pending",
            json={"limit": 7, "lookback_days": 3, "trigger_source": "auto"},
        )
        body = response.json()
        assert response.status_code == 200
        assert body["results"][0]["limit"] == 7
        assert body["results"][0]["lookback_days"] == 3
        assert body["results"][0]["trigger_source"] == "auto"
    finally:
        api.MatchService = old
