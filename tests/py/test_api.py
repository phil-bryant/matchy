#R001: Python test lane coverage for health endpoint behavior.
#R005: Python test lane coverage for missing-transaction HTTP mapping.
#R010: Python test lane coverage for pending-run endpoint delegation.
#R015: Python test lane coverage for startup CLDR currencies cache refresh.
#R055: Python test lane coverage for API Bearer-auth protections on mutating endpoints.

from fastapi.testclient import TestClient
import pytest

import matchy.api as api
from matchy.api import create_app


def _auth_headers(token: str = "test-matchy-api-token") -> dict[str, str]:
    #R480: Test helper reuses configured auth header shape for startup/logging and endpoint path checks.
    return {"Authorization": f"Bearer {token}"}


def _write_token_headers(token: str = "test-matchy-api-token") -> dict[str, str]:
    #R055: Test helper supports write-token header auth paths used by DAST profiles.
    return {"X-Matchy-Write-Token": token}


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
        #R480: Test helper supports startup-path checks for app boot behavior.
        def __init__(self, settings):
            self._settings = settings

        #R480: Test helper supports startup-path checks for app boot behavior.
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
        #R490: Test helper covers run endpoint ValueError mapping behavior.
        def match_transaction(self, transaction_id, trigger_source="manual", force_rematch=False):
            raise ValueError("Unknown transaction_id: missing")

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/runs",
            json={"transaction_ids": ["missing"], "trigger_source": "manual"},
            headers=_auth_headers(),
        )
        assert response.status_code == 404
        assert response.json().get("detail") == "No transaction matched the supplied transaction_id."
    finally:
        api.MatchService = old


def test_api_run_endpoint_rejects_empty_transaction_id_with_422() -> None:
    #R005: API request model rejects empty transaction ids before service execution.
    #R005-T02: Python test lane exists for run endpoint request validation.
    response = TestClient(create_app()).post(
        "/v1/matchy/runs",
        json={"transaction_ids": [""], "trigger_source": "manual"},
        headers=_auth_headers(),
    )
    assert response.status_code == 422


def test_api_run_endpoint_uses_atomic_batch_matcher_when_service_supports_it() -> None:
    #R490: Run endpoint prefers atomic batch matcher when the service exposes that capability.
    #R490-T01: Python test lane exists for run endpoint batch-dispatch requirement.
    calls = []

    class StubService:
        #R490: Test helper covers run endpoint batch dispatch behavior.
        def match_transactions_atomic(self, transaction_ids, trigger_source="manual", force_rematch=False):
            calls.append((transaction_ids, trigger_source, force_rematch))
            return [{"transaction_id": transaction_id, "run_id": 1} for transaction_id in transaction_ids]

        #R490: Test helper covers run endpoint batch dispatch behavior.
        def match_transaction(self, transaction_id, trigger_source="manual", force_rematch=False):
            raise AssertionError("run endpoint should use match_transactions_atomic when available")

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/runs",
            json={"transaction_ids": ["txn_1", "txn_2"], "trigger_source": "manual", "force_rematch": True},
            headers=_auth_headers(),
        )
        assert response.status_code == 200
        assert [item["transaction_id"] for item in response.json()["results"]] == ["txn_1", "txn_2"]
        assert calls == [(["txn_1", "txn_2"], "manual", True)]
    finally:
        api.MatchService = old


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/v1/matchy/runs", {"transaction_ids": ["txn_1"], "trigger_source": "manual"}),
        ("/v1/matchy/runs/pending", {"limit": 7, "lookback_days": 3, "trigger_source": "auto"}),
        ("/v1/matchy/confirm", {"transaction_id": "txn_123", "email_message_id": "eml_456", "note": "ok"}),
    ],
)
def test_api_mutating_endpoints_require_bearer_auth(path: str, payload: dict) -> None:
    #R055: Mutating endpoints require Authorization: Bearer <token>.
    #R055-T01: Missing auth header is rejected with HTTP 401.
    response = TestClient(create_app()).post(path, json=payload)
    assert response.status_code == 401


def test_api_mutating_endpoints_reject_wrong_bearer_token() -> None:
    #R055: Invalid auth token is rejected even when the header shape is valid.
    #R055-T02: Wrong bearer token returns HTTP 401.
    response = TestClient(create_app()).post(
        "/v1/matchy/runs/pending",
        json={"limit": 7, "lookback_days": 3, "trigger_source": "auto"},
        headers=_auth_headers(token="wrong-token"),
    )
    assert response.status_code == 401


def test_api_mutating_endpoints_accept_write_token_header_alias() -> None:
    #R055-T03: Mutating endpoints accept write-token header aliases for scanner compatibility.
    class StubService:
        #R495: Test helper covers pending endpoint delegation behavior.
        def match_pending_transactions(self, limit=100, lookback_days=14, trigger_source="auto", force_rematch=False):
            return [{"ok": True}]

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/runs/pending",
            json={"limit": 7, "lookback_days": 3, "trigger_source": "auto"},
            headers=_write_token_headers(),
        )
        assert response.status_code == 200
    finally:
        api.MatchService = old


def test_api_mutating_endpoints_respect_matchy_write_enabled_flag(monkeypatch) -> None:
    #R055-T04: Mutating endpoints fail closed when MATCHY_WRITE_ENABLED=false.
    monkeypatch.setenv("MATCHY_WRITE_ENABLED", "false")
    response = TestClient(create_app()).post(
        "/v1/matchy/runs",
        json={"transaction_ids": ["txn_1"], "trigger_source": "manual"},
        headers=_auth_headers(),
    )
    assert response.status_code == 503
    assert "MATCHY_WRITE_ENABLED=false" in response.json().get("detail", "")


def test_api_mutating_endpoints_apply_rate_limit_window(monkeypatch) -> None:
    #R055-T05: Mutating endpoints enforce request-rate throttling.
    monkeypatch.setenv("MATCHY_MUTATION_RATE_LIMIT_MAX_REQUESTS", "3")
    monkeypatch.setenv("MATCHY_MUTATION_RATE_LIMIT_WINDOW_SECONDS", "60")

    class StubService:
        #R495: Test helper covers pending endpoint delegation behavior.
        def match_pending_transactions(self, limit=100, lookback_days=14, trigger_source="auto", force_rematch=False):
            return [{"ok": True}]

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        client = TestClient(create_app())
        for _ in range(3):
            response = client.post(
                "/v1/matchy/runs/pending",
                json={"limit": 7, "lookback_days": 3, "trigger_source": "auto"},
                headers=_auth_headers(),
            )
            assert response.status_code == 200
        blocked = client.post(
            "/v1/matchy/runs/pending",
            json={"limit": 7, "lookback_days": 3, "trigger_source": "auto"},
            headers=_auth_headers(),
        )
        assert blocked.status_code == 429
    finally:
        api.MatchService = old


def test_api_openapi_docs_are_disabled_by_default() -> None:
    #R001: OpenAPI/docs endpoints are not exposed unless explicitly enabled.
    client = TestClient(create_app())
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404


def test_api_pending_run_endpoint_delegates_to_service_batch_matcher() -> None:
    #R010: Pending-run endpoint delegates to service batch matching with validated request fields.
    #R010-T01: Python test lane exists for pending-run endpoint requirement.
    #R495: Pending-run endpoint delegates to service batch matching with validated request fields.
    #R495-T01: Python test lane exists for pending-run endpoint requirement.
    class StubService:
        #R495: Test helper covers pending endpoint delegation behavior.
        def match_pending_transactions(self, limit=100, lookback_days=14, trigger_source="auto", force_rematch=False):
            return [{"ok": True, "limit": limit, "lookback_days": lookback_days, "trigger_source": trigger_source}]

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/runs/pending",
            json={"limit": 7, "lookback_days": 3, "trigger_source": "auto"},
            headers=_auth_headers(),
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
    #R500: Confirm endpoint accepts transaction+email and delegates.
    #R500-T01: Python test lane exists for confirm API endpoint.
    calls = []

    class StubService:
        #R500: Test helper covers confirm endpoint delegation behavior.
        def confirm_match(self, transaction_id, email_message_id, note=None):
            calls.append((transaction_id, email_message_id, note))
            return {"status": "confirmed", "match_id": 123}

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/confirm",
            json={"transaction_id": "txn_123", "email_message_id": "eml_456", "note": "user note"},
            headers=_auth_headers(),
        )
        assert response.status_code == 200
        assert calls == [("txn_123", "eml_456", "user note")]
    finally:
        api.MatchService = old


def test_api_confirm_endpoint_maps_unknown_ids_to_http_404() -> None:
    #R045: Confirm endpoint maps service ValueError to HTTP 404.
    #R045-T01: Python test lane exists for confirm endpoint 404 mapping.
    #R500: Confirm endpoint maps service ValueError to HTTP 404.
    #R500-T02: Python test lane exists for confirm endpoint 404 mapping.
    class StubService:
        #R500: Test helper covers confirm endpoint ValueError mapping.
        def confirm_match(self, transaction_id, email_message_id, note=None):
            raise ValueError(f"Unknown transaction_id or email_message_id for confirmation: {transaction_id}/{email_message_id}")

    old = api.MatchService
    api.MatchService = lambda settings: StubService()
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/confirm",
            json={"transaction_id": "txn_missing", "email_message_id": "eml_missing", "note": "n"},
            headers=_auth_headers(),
        )
        assert response.status_code == 404
        assert response.json().get("detail") == "Unknown transaction or email message for confirmation."
    finally:
        api.MatchService = old


def test_api_confirm_endpoint_rejects_note_with_null_byte() -> None:
    #R045: Confirm request validation rejects notes containing null bytes.
    #R045-T03: Python test lane exists for confirm endpoint note sanitization.
    response = TestClient(create_app()).post(
        "/v1/matchy/confirm",
        json={"transaction_id": "txn_123", "email_message_id": "eml_456", "note": "ok\u0000bad"},
        headers=_auth_headers(),
    )
    assert response.status_code == 422


def test_api_startup_log_emits_when_enabled(monkeypatch, capsys) -> None:
    #R480-T01: Startup logging emits elapsed-phase lines only when MATCHY_STARTUP_LOG=true.
    monkeypatch.setenv("MATCHY_STARTUP_LOG", "true")
    api._startup_log(0.0, "phase-check", "detail=x")
    captured = capsys.readouterr().out
    assert "phase-check" in captured
    assert "detail=x" in captured


def test_api_service_dependency_maps_constructor_failures_to_http_503() -> None:
    #R485-T01: Endpoint dependency maps MatchService construction failures to HTTP 503.
    old = api.MatchService
    api.MatchService = lambda settings: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        response = TestClient(create_app()).post(
            "/v1/matchy/runs",
            json={"transaction_ids": ["txn_1"], "trigger_source": "manual"},
            headers=_auth_headers(),
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Match service is unavailable."
    finally:
        api.MatchService = old
