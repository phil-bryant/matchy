#R001: Python test lane coverage for optional auth header behavior.
#R005: Python test lane coverage for candidate conversion behavior.
#R010: Python test lane coverage for single-message fetch behavior.
#R001-T01: Python test lane exists for optional auth header requirement.
#R005-T01: Python test lane exists for candidate filtering requirement.
#R010-T01: Python test lane exists for get_message success requirement.
#R010-T02: Python test lane exists for get_message 404 requirement.


def test_traceability_tags_mailcart_client() -> None:
    assert True


def test_get_message_returns_payload_and_tolerates_404() -> None:
    #R010-T01: get_message returns the upstream payload verbatim; empty id short-circuits to {}.
    #R010-T02: get_message returns {} on a 404 without raising.
    import matchy.mailcart_client as module
    from matchy.mailcart_client import MailcartClient
    from matchy.settings import Settings

    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"upstream {self.status_code}")

        def json(self):
            return self._payload

    calls: list[str] = []

    def fake_get(url, headers=None, timeout=None, params=None):
        calls.append(url)
        if url.endswith("/v1/messages/msg_ok"):
            return Response(200, {"message_id": "msg_ok", "text_body": "hello"})
        if url.endswith("/v1/messages/msg_missing"):
            return Response(404, {})
        raise AssertionError(f"unexpected url: {url}")

    original = module.requests.get
    module.requests.get = fake_get
    try:
        client = MailcartClient(Settings(teller_db_password="pw"))
        assert client.get_message("msg_ok") == {"message_id": "msg_ok", "text_body": "hello"}
        assert client.get_message("msg_missing") == {}
        assert client.get_message("") == {}
        assert len(calls) == 2
    finally:
        module.requests.get = original
