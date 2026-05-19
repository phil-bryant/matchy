#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R010-T02

@test "mailcart_client headers include optional bearer token" {
  #R001: Authorization header appears only when token is configured.
  #R001-T01: Verify header behavior with and without token.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.mailcart_client import MailcartClient
from matchy.settings import Settings
with_token = MailcartClient(Settings(teller_db_password="pw", mailcart_service_token="tok"))
without_token = MailcartClient(Settings(teller_db_password="pw", mailcart_service_token=""))
print(("Authorization" in with_token._headers()) and ("Authorization" not in without_token._headers()))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "mailcart_client search filters rows missing message ids" {
  #R005: Search response rows are transformed and invalid ids are dropped.
  #R005-T01: Verify empty message_id rows are filtered out.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
import matchy.mailcart_client as module
from matchy.mailcart_client import MailcartClient
from matchy.settings import Settings

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
    print(len(rows) == 1 and rows[0].message_id == "m1")
finally:
    module.requests.get = original
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "mailcart_client get_message returns payload dict and handles 404" {
  #R010: get_message proxies single-message envelopes and tolerates 404 misses.
  #R010-T01: Verify get_message returns the upstream payload verbatim and short-circuits empty ids.
  #R010-T02: Verify get_message returns an empty dict on 404 without raising.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
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
    checks = [
        ok == {"message_id": "msg_ok", "subject": "S", "sender": "x@y", "text_body": "hello"},
        miss == {},
        empty == {},
        len(calls) == 2,
        calls[0].endswith("/v1/messages/msg_ok"),
        calls[1].endswith("/v1/messages/msg_missing"),
    ]
    print(all(checks))
finally:
    module.requests.get = original
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
