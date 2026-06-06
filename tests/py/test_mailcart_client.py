#R001: Python test lane coverage for mailcart authorization headers.
#R005: Python test lane coverage for search response filtering.
#R010: Python test lane coverage for get_message behavior.
#R015: Python test lane coverage for https-only base URL enforcement.

import matchy.mailcart_client as module
from types import SimpleNamespace
from matchy.mailcart_client import MailcartClient
from matchy.settings import Settings


def test_mailcart_client_headers_include_optional_bearer_token() -> None:
    #R001: Authorization header appears only when token is configured.
    #R001-T01: Python test lane exists for authorization header requirement.
    with_token = MailcartClient(Settings(mailcart_service_token="tok"))
    without_token = MailcartClient(Settings(mailcart_service_token=""))
    assert "Authorization" in with_token._headers()
    assert "Authorization" not in without_token._headers()


def test_mailcart_client_search_filters_rows_missing_message_ids() -> None:
    #R005: Search response rows are transformed and invalid ids are dropped.
    #R005-T01: Python test lane exists for search filtering requirement.
    class Response:
        status_code = 200

        #R005: Test helper supports this requirement-focused scenario.
        def raise_for_status(self):
            return None

        #R005: Test helper supports this requirement-focused scenario.
        def json(self):
            return {"messages": [
                {"message_id": "m1", "subject": "a", "preview": "b", "received_at": "2024-01-01T00:00:00Z"},
                {"message_id": "", "subject": "x", "preview": "y", "received_at": "2024-01-01T00:00:00Z"},
            ]}

    original = module.requests.get
    module.requests.get = lambda *_args, **kwargs: Response()
    try:
        rows = MailcartClient(Settings()).search_candidates("x")
        assert len(rows) == 1
        assert rows[0].message_id == "m1"
    finally:
        module.requests.get = original


def test_mailcart_client_get_message_returns_payload_dict_and_handles_404() -> None:
    #R010: get_message proxies single-message envelopes and tolerates 404 misses.
    #R010-T01: Python test lane exists for get_message payload requirement.
    class Response:
        #R010: Test helper supports this requirement-focused scenario.
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        #R010: Test helper supports this requirement-focused scenario.
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"upstream {self.status_code}")

        #R010: Test helper supports this requirement-focused scenario.
        def json(self):
            return self._payload

    calls = []

    #R010: Test helper supports this requirement-focused scenario.
    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith("/v1/messages/msg_ok"):
            return Response(200, {"message_id": "msg_ok", "subject": "S", "sender": "x@y", "text_body": "hello"})
        if url.endswith("/v1/messages/msg_missing"):
            return Response(404, {})
        raise AssertionError(f"unexpected url: {url}")

    original = module.requests.get
    module.requests.get = fake_get
    try:
        client = MailcartClient(Settings())
        ok = client.get_message("msg_ok")
        miss = client.get_message("msg_missing")
        empty = client.get_message("")
        assert ok == {"message_id": "msg_ok", "subject": "S", "sender": "x@y", "text_body": "hello"}
        assert miss == {}
        assert empty == {}
        assert len(calls) == 2
        assert calls[0].endswith("/v1/messages/msg_ok")
        assert calls[1].endswith("/v1/messages/msg_missing")
    finally:
        module.requests.get = original


def test_mailcart_client_get_message_retries_once_for_502_then_succeeds() -> None:
    #R010: get_message retries transient 502 once before returning payload.
    #R010-T02: Python test lane exists for get_message 404 requirement.
    class Response:
        #R010: Test helper supports this requirement-focused scenario.
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        #R010: Test helper supports this requirement-focused scenario.
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"upstream {self.status_code}")

        #R010: Test helper supports this requirement-focused scenario.
        def json(self):
            return self._payload

    calls = []

    #R010: Test helper supports this requirement-focused scenario.
    def fake_get(url, timeout=None, **kwargs):
        calls.append((url, timeout))
        if len(calls) == 1:
            return Response(502, {})
        return Response(200, {"message_id": "msg_ok", "text_body": "hello"})

    original_get = module.requests.get
    original_sleep = module.time.sleep
    module.requests.get = fake_get
    module.time.sleep = lambda _seconds: None
    try:
        client = MailcartClient(Settings(mailcart_get_message_timeout_seconds=2))
        payload = client.get_message("msg_ok")
        assert payload == {"message_id": "msg_ok", "text_body": "hello"}
        assert len(calls) == 2
    finally:
        module.requests.get = original_get
        module.time.sleep = original_sleep


def test_mailcart_client_resolves_explicit_ca_bundle_override(tmp_path, monkeypatch) -> None:
    #R045: An explicit MATCHY_MAILCART_CA_BUNDLE path is used to verify Mailcart TLS.
    ca_file = tmp_path / "custom-ca.pem"
    ca_file.write_text("dummy", encoding="utf-8")
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    client = MailcartClient(Settings(mailcart_ca_bundle=str(ca_file)))
    assert client._verify == str(ca_file)


def test_mailcart_client_passes_ca_bundle_to_search_request(tmp_path, monkeypatch) -> None:
    #R045: The resolved CA bundle is forwarded as the requests verify argument.
    ca_file = tmp_path / "custom-ca.pem"
    ca_file.write_text("dummy", encoding="utf-8")
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    captured = {}

    class Response:
        status_code = 200

        #R045: Test helper supports this requirement-focused scenario.
        def raise_for_status(self):
            return None

        #R045: Test helper supports this requirement-focused scenario.
        def json(self):
            return {"messages": []}

    #R045: Test helper supports this requirement-focused scenario.
    def fake_get(*_args, **kwargs):
        captured["verify"] = kwargs.get("verify")
        return Response()

    original = module.requests.get
    module.requests.get = fake_get
    try:
        client = MailcartClient(Settings(mailcart_ca_bundle=str(ca_file)))
        client.search_candidates("subject:x")
        assert captured["verify"] == str(ca_file)
    finally:
        module.requests.get = original


def test_mailcart_client_rejects_non_https_base_url() -> None:
    #R015-T01: Mailcart client must fail fast when base URL is not https.
    settings = SimpleNamespace(
        mailcart_service_base_url="http://127.0.0.1:8788",
        mailcart_service_token="",
        mailcart_get_message_timeout_seconds=3,
    )
    try:
        MailcartClient(settings)
    except RuntimeError as exc:
        assert "must use https" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for non-https Mailcart base URL")


def test_mailcart_client_ca_bundle_precedence(monkeypatch) -> None:
    #R045-T01: _resolve_ca_bundle prefers explicit MATCHY_MAILCART_CA_BUNDLE, then REQUESTS_CA_BUNDLE/SSL_CERT_FILE, then mkcert fallback.
    from matchy.mailcart_client import MailcartClient
    import os as _os
    real_exists = _os.path.exists
    monkeypatch.setattr(_os.path, "exists", lambda p: True if p in {"/explicit.pem", "/req.pem", "/ssl.pem"} else real_exists(p))
    # Explicit override wins
    s1 = SimpleNamespace(mailcart_ca_bundle="/explicit.pem")
    assert MailcartClient._resolve_ca_bundle(s1) == "/explicit.pem"
    # REQUESTS_CA_BUNDLE next
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/req.pem")
    s2 = SimpleNamespace(mailcart_ca_bundle="")
    assert MailcartClient._resolve_ca_bundle(s2) == "/req.pem"
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    # SSL_CERT_FILE fallback
    monkeypatch.setenv("SSL_CERT_FILE", "/ssl.pem")
    s3 = SimpleNamespace(mailcart_ca_bundle="")
    assert MailcartClient._resolve_ca_bundle(s3) == "/ssl.pem"


def test_mailcart_client_rejects_missing_explicit_ca_bundle() -> None:
    #R045-T02: Explicit MATCHY_MAILCART_CA_BUNDLE path must exist; missing files fail fast.
    settings = SimpleNamespace(
        mailcart_service_base_url="https://127.0.0.1:8788",
        mailcart_service_token="",
        mailcart_get_message_timeout_seconds=3,
        mailcart_search_timeout_seconds=45,
        mailcart_ca_bundle="/definitely/missing/ca.pem",
        mailcart_startup_healthcheck_timeout_seconds=2,
    )
    try:
        MailcartClient(settings)
    except RuntimeError as exc:
        assert "MATCHY_MAILCART_CA_BUNDLE points to a missing file" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for missing explicit CA bundle")


def test_mailcart_client_match_service_runs_startup_preflight_once(monkeypatch) -> None:
    #R050-T01: MatchService constructor triggers Mailcart startup preflight once when enabled.
    import matchy.service as service_module
    calls = {"preflight": 0}

    class StubMailcartClient:
        #R050: Test helper supports this requirement-focused scenario.
        def __init__(self, _settings):
            pass

        #R050: Test helper supports this requirement-focused scenario.
        def startup_preflight_healthcheck(self):
            calls["preflight"] += 1

    class StubCldrCache:
        #R050: Test helper supports this requirement-focused scenario.
        def __init__(self, _settings):
            pass

        #R050: Test helper supports this requirement-focused scenario.
        def currency_matcher(self):
            return object()

    monkeypatch.setattr(service_module, "MatchRepository", lambda _settings: object())
    monkeypatch.setattr(service_module, "MailcartClient", StubMailcartClient)
    monkeypatch.setattr(service_module, "AiRanker", lambda _settings: object())
    monkeypatch.setattr(service_module, "CldrCurrenciesCache", StubCldrCache)
    settings = SimpleNamespace(mailcart_startup_healthcheck_enabled=True, mailcart_failure_cooldown_seconds=15)
    service_module.MatchService(settings)
    assert calls["preflight"] == 1


def test_mailcart_client_startup_preflight_passes_verify_and_timeout(tmp_path) -> None:
    #R050-T02: Startup preflight uses the same base URL/verify configuration as runtime calls.
    ca_file = tmp_path / "custom-ca.pem"
    ca_file.write_text("dummy", encoding="utf-8")
    captured = {}

    class Response:
        status_code = 200

        #R050: Test helper supports this requirement-focused scenario.
        def raise_for_status(self):
            return None

    #R050: Test helper supports this requirement-focused scenario.
    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["verify"] = kwargs.get("verify")
        captured["timeout"] = kwargs.get("timeout")
        return Response()

    original = module.requests.get
    module.requests.get = fake_get
    try:
        client = MailcartClient(
            Settings(
                mailcart_ca_bundle=str(ca_file),
                mailcart_startup_healthcheck_timeout_seconds=4,
            )
        )
        client.startup_preflight_healthcheck()
    finally:
        module.requests.get = original
    assert captured["url"].endswith("/health")
    assert captured["verify"] == str(ca_file)
    assert captured["timeout"] == 4


def test_mailcart_client_startup_preflight_failure_includes_transport_context(tmp_path) -> None:
    #R050-T03: Preflight transport failures include actionable base_url + verify diagnostics.
    ca_file = tmp_path / "custom-ca.pem"
    ca_file.write_text("dummy", encoding="utf-8")

    #R050: Test helper supports this requirement-focused scenario.
    def fake_get(*_args, **_kwargs):
        raise module.requests.exceptions.ConnectionError("Connection aborted")

    original = module.requests.get
    module.requests.get = fake_get
    try:
        client = MailcartClient(Settings(mailcart_ca_bundle=str(ca_file)))
        try:
            client.startup_preflight_healthcheck()
        except RuntimeError as exc:
            message = str(exc)
            assert "Mailcart startup preflight failed" in message
            assert "base_url=https://127.0.0.1:8788" in message
            assert f"verify={str(ca_file)}" in message
        else:
            raise AssertionError("expected RuntimeError from startup preflight")
    finally:
        module.requests.get = original
