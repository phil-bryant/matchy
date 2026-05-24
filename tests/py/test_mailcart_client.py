#R001: Python test lane coverage for mailcart authorization headers.
#R005: Python test lane coverage for search response filtering.
#R010: Python test lane coverage for get_message behavior.
#R001-T01: Python test lane exists for authorization header requirement.
#R005-T01: Python test lane exists for search filtering requirement.
#R010-T01: Python test lane exists for get_message payload requirement.
#R010-T02: Python test lane exists for get_message 404 requirement.

import matchy.mailcart_client as module
from matchy.mailcart_client import MailcartClient
from matchy.settings import Settings


def test_mailcart_client_headers_include_optional_bearer_token() -> None:
    #R001: Authorization header appears only when token is configured.
    with_token = MailcartClient(Settings(teller_db_password="pw", mailcart_service_token="tok"))
    without_token = MailcartClient(Settings(teller_db_password="pw", mailcart_service_token=""))
    assert "Authorization" in with_token._headers()
    assert "Authorization" not in without_token._headers()


def test_mailcart_client_search_filters_rows_missing_message_ids() -> None:
    #R005: Search response rows are transformed and invalid ids are dropped.
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"messages": [
                {"message_id": "m1", "subject": "a", "preview": "b", "received_at": "2024-01-01T00:00:00Z"},
                {"message_id": "", "subject": "x", "preview": "y", "received_at": "2024-01-01T00:00:00Z"},
            ]}

    original = module.requests.get
    module.requests.get = lambda *args, **kwargs: Response()
    try:
        rows = MailcartClient(Settings(teller_db_password="pw")).search_candidates("x")
        assert len(rows) == 1
        assert rows[0].message_id == "m1"
    finally:
        module.requests.get = original


def test_mailcart_client_get_message_returns_payload_dict_and_handles_404() -> None:
    #R010: get_message proxies single-message envelopes and tolerates 404 misses.
    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"upstream {self.status_code}")

        def json(self):
            return self._payload

    calls = []

    def fake_get(url, headers=None, timeout=None, params=None):
        calls.append(url)
        if url.endswith("/v1/messages/msg_ok"):
            return Response(200, {"message_id": "msg_ok", "subject": "S", "sender": "x@y", "text_body": "hello"})
        if url.endswith("/v1/messages/msg_missing"):
            return Response(404, {})
        raise AssertionError(f"unexpected url: {url}")

    original = module.requests.get
    module.requests.get = fake_get
    try:
        client = MailcartClient(Settings(teller_db_password="pw"))
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
    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"upstream {self.status_code}")

        def json(self):
            return self._payload

    calls = []

    def fake_get(url, headers=None, timeout=None, params=None):
        calls.append((url, timeout))
        if len(calls) == 1:
            return Response(502, {})
        return Response(200, {"message_id": "msg_ok", "text_body": "hello"})

    original_get = module.requests.get
    original_sleep = module.time.sleep
    module.requests.get = fake_get
    module.time.sleep = lambda _seconds: None
    try:
        client = MailcartClient(Settings(teller_db_password="pw", mailcart_get_message_timeout_seconds=2))
        payload = client.get_message("msg_ok")
        assert payload == {"message_id": "msg_ok", "text_body": "hello"}
        assert len(calls) == 2
    finally:
        module.requests.get = original_get
        module.time.sleep = original_sleep
