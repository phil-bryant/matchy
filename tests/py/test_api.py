#R001: Python test lane coverage for health endpoint behavior.
#R005: Python test lane coverage for missing-transaction HTTP mapping.
#R010: Python test lane coverage for pending-run endpoint delegation.
#R015: Python test lane coverage for startup CLDR currencies cache refresh.

from fastapi.testclient import TestClient

import matchy.api as api
from matchy.api import create_app


def test_api_health_endpoint_returns_status_ok() -> None:
    #R001: Health endpoint returns deterministic status payload.
    #R001-T01: Python test lane exists for health endpoint requirement.
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_api_create_app_refreshes_cldr_currencies_cache_when_enabled(monkeypatch) -> None:
    #R015: App startup refreshes the local CLDR currencies cache when the startup feature flag is enabled.
    #R015-T01: Python test lane exists for startup CLDR cache refresh requirement.
    calls = []

    class StubCache:
        def __init__(self, settings):
            self._settings = settings

        def refresh(self):
            calls.append(self._settings.cldr_currencies_cache_path)
            return {"updated": True, "version": "sha-1", "cache_path": self._settings.cldr_currencies_cache_path}

    monkeypatch.setenv("MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED", "true")
    monkeypatch.setenv("MATCHY_CLDR_CURRENCIES_CACHE_PATH", "/tmp/matchy-currencies.json")
    monkeypatch.setattr(api, "CldrCurrenciesCache", StubCache)
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert calls == ["/tmp/matchy-currencies.json"]


def test_api_run_endpoint_maps_unknown_transaction_to_http_404() -> None:
    #R005: ValueError from service is converted into HTTP 404.
    #R005-T01: Python test lane exists for 404 mapping requirement.
    class StubService:
        def match_transaction(self, transaction_id, trigger_source="manual", force_rematch=False):
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


def test_api_run_endpoint_rejects_empty_transaction_id_with_422() -> None:
    #R005: API request model rejects empty transaction ids before service execution.
    #R005-T02: Python test lane exists for run endpoint request validation.
    response = TestClient(create_app()).post(
        "/v1/matchy/runs",
        json={"transaction_ids": [""], "trigger_source": "manual"},
    )
    assert response.status_code == 422


def test_api_pending_run_endpoint_delegates_to_service_batch_matcher() -> None:
    #R010: Pending-run endpoint delegates to service batch matching with validated request fields.
    #R010-T01: Python test lane exists for pending-run endpoint requirement.
    class StubService:
        def match_pending_transactions(self, limit=100, lookback_days=14, trigger_source="auto", force_rematch=False):
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


def test_api_confirm_endpoint_delegates_to_service_confirm() -> None:
    #R045: Confirm endpoint accepts transaction+email and delegates.
    #R045-T02: Python test lane exists for confirm API endpoint.
    calls = []

    class StubService:
        def confirm_match(self, transaction_id, email_message_id, note=None):
            calls.append((transaction_id, email_message_id, note))
            return {"status": "confirmed", "match_id": 123}

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/confirm",
            json={"transaction_id": "txn_123", "email_message_id": "eml_456", "note": "user note"},
        )
        assert response.status_code == 200
        assert calls == [("txn_123", "eml_456", "user note")]
    finally:
        api.MatchService = old


def test_api_confirm_endpoint_maps_unknown_ids_to_http_404() -> None:
    #R045: Confirm endpoint maps service ValueError to HTTP 404.
    #R045-T01: Python test lane exists for confirm endpoint 404 mapping.
    class StubService:
        def confirm_match(self, transaction_id, email_message_id, note=None):
            raise ValueError(f"Unknown transaction_id or email_message_id for confirmation: {transaction_id}/{email_message_id}")

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/confirm",
            json={"transaction_id": "txn_missing", "email_message_id": "eml_missing", "note": "n"},
        )
        assert response.status_code == 404
    finally:
        api.MatchService = old


def test_api_confirm_endpoint_rejects_note_with_null_byte() -> None:
    #R045: Confirm request validation rejects notes containing null bytes.
    #R045-T03: Python test lane exists for confirm endpoint note sanitization.
    response = TestClient(create_app()).post(
        "/v1/matchy/confirm",
        json={"transaction_id": "txn_123", "email_message_id": "eml_456", "note": "ok\u0000bad"},
    )
    assert response.status_code == 422
