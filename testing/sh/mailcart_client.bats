#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

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
