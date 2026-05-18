#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "mailcart_client headers include optional bearer token" {
  #R001: Authorization header appears only when token is configured.
  #R001-T01: Verify header behavior with and without token.
  run env PYTHONPATH="$(pwd)" python3 -c "from matchy.mailcart_client import MailcartClient; from matchy.settings import Settings; c1=MailcartClient(Settings(teller_db_password='pw', mailcart_service_token='tok')); c2=MailcartClient(Settings(teller_db_password='pw', mailcart_service_token='')); print(('Authorization' in c1._headers()) and ('Authorization' not in c2._headers()))"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "mailcart_client search filters rows missing message ids" {
  #R005: Search response rows are transformed and invalid ids are dropped.
  #R005-T01: Verify empty message_id rows are filtered out.
  run env PYTHONPATH="$(pwd)" python3 -c "import matchy.mailcart_client as m; from matchy.mailcart_client import MailcartClient; from matchy.settings import Settings; class Resp:
  status_code=200
  def raise_for_status(self):
   return None
  def json(self):
   return {'messages':[{'message_id':'m1','subject':'a','preview':'b','received_at':'2024-01-01T00:00:00Z'},{'message_id':'','subject':'x','preview':'y','received_at':'2024-01-01T00:00:00Z'}]}; old=m.requests.get; m.requests.get=lambda *a, **k: Resp(); out=MailcartClient(Settings(teller_db_password='pw')).search_candidates('x'); m.requests.get=old; print(len(out)==1 and out[0].message_id=='m1')"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
