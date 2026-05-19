#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R015-T02 #R020-T01 #R020-T02 #R020-T03 #R025-T01

@test "service raises valueerror for unknown transactions" {
  #R001: Unknown transaction IDs raise ValueError.
  #R001-T01: Verify error path when repository returns no transaction.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.service import MatchService

class Repo:
    class Ctx:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    def session(self):
        return Repo.Ctx()

    def load_transaction(self, session, transaction_id):
        return None

service = object.__new__(MatchService)
service._repository = Repo()
ok = False
try:
    service.match_transaction("missing")
except ValueError as exc:
    ok = "Unknown transaction_id" in str(exc)
print(ok)
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service query builders normalize and filter tokens" {
  #R005: Query helpers produce deterministic normalized text tokens.
  #R005-T01: Verify normalized query and broad query outputs.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.service import MatchService

service = object.__new__(MatchService)
query = service._build_query("Payment #1234 at DoorDash.com", "DoorDash")
broad = service._build_broad_query("Payment #1234 at DoorDash.com", "DoorDash")
print(query == "doordash payment doordash" and broad == "payment")
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service enriches candidate bodies with full mailcart message body before scoring" {
  #R015: _enrich_candidate_bodies replaces body_text with full Mailcart body and tolerates per-id failures.
  #R015-T01: Verify enriched candidate carries fetched body while a 404'd candidate keeps its original body_text.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from datetime import datetime, timezone
from types import SimpleNamespace

from matchy.models import EmailCandidate
from matchy.service import MatchService

class FakeClient:
    def __init__(self):
        self.calls = []
    def get_message(self, message_id):
        self.calls.append(message_id)
        if message_id == "msg_ok":
            return {"text_body": "Total fare $35.99 thank you", "subject": "Receipt", "sender": "x@y"}
        if message_id == "msg_html":
            return {"html_body": "<p>$35.99</p>", "subject": "Receipt", "sender": "x@y"}
        return {}

cands = [
    EmailCandidate(message_id="msg_ok",      subject="Your ride", preview="preview only",
                   received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview only"),
    EmailCandidate(message_id="msg_missing", subject="Your ride", preview="preview only",
                   received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview only"),
    EmailCandidate(message_id="msg_html",    subject="Your ride", preview="preview only",
                   received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview only"),
]

service = object.__new__(MatchService)
service._settings = SimpleNamespace(mailcart_body_enrichment_enabled=True, mailcart_body_enrichment_limit=75)
service._mailcart_client = FakeClient()

out = service._enrich_candidate_bodies(cands, transaction_id="txn_test")
ok = out[0].body_text == "Total fare $35.99 thank you"
miss = out[1].body_text == "preview only" and out[1].message_id == "msg_missing"
html = out[2].body_text == "<p>$35.99</p>"
called = service._mailcart_client.calls == ["msg_ok", "msg_missing", "msg_html"]
print(ok and miss and html and called)
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service skips body enrichment when feature flag is disabled" {
  #R015: Enrichment is gated by mailcart_body_enrichment_enabled.
  #R015-T02: Verify get_message is not called when the flag is False and candidates pass through unchanged.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from datetime import datetime, timezone
from types import SimpleNamespace

from matchy.models import EmailCandidate
from matchy.service import MatchService

class FakeClient:
    def __init__(self):
        self.calls = []
    def get_message(self, message_id):
        self.calls.append(message_id)
        return {"text_body": "should-not-appear"}

cand = EmailCandidate(message_id="m1", subject="s", preview="preview text",
                      received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview text")

service = object.__new__(MatchService)
service._settings = SimpleNamespace(mailcart_body_enrichment_enabled=False, mailcart_body_enrichment_limit=75)
service._mailcart_client = FakeClient()
out = service._enrich_candidate_bodies([cand], transaction_id="txn_test")
print(out == [cand] and service._mailcart_client.calls == [])
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service short-circuits AI call when candidate set is unchanged since last run" {
  #R020: match_transaction returns skipped=True when (model, prompt, candidate set) match last run.
  #R020-T01: Verify no run is created, the AI ranker is not invoked, and skipped=True is returned.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from datetime import datetime, timezone
from decimal import Decimal
from matchy.ai_ranker import PROMPT_VERSION
from matchy.models import EmailCandidate, TransactionInput
from matchy.service import MatchService

class FakeRepo:
    class Ctx:
        def __init__(self, session): self.session = session
        def __enter__(self): return self.session
        def __exit__(self, *exc): return False
    def __init__(self, txn, last_summary, active):
        self.txn = txn; self.last_summary = last_summary; self.active = active
        self.create_run_calls = 0
    def session(self): return FakeRepo.Ctx(object())
    def load_transaction(self, session, transaction_id): return self.txn
    def read_last_run_summary(self, session, transaction_id): return self.last_summary
    def read_active_match_summary(self, session, transaction_id): return self.active
    def create_run(self, **kwargs): self.create_run_calls += 1; return 999

class FakeClient:
    def __init__(self, results): self._results = results; self.search_calls = 0
    def search_candidates(self, query, limit=75):
        self.search_calls += 1
        return self._results.pop(0) if self._results else []
    def get_message(self, mid): raise AssertionError("should not be called on cache hit")

class FakeRanker:
    def __init__(self, model): self._model = model
    def planned_model_name(self): return self._model
    def select(self, txn, ranked): raise AssertionError("AI ranker must not be called on cache hit")

txn = TransactionInput("txn1","acc",Decimal("35.99"),datetime(2026,5,5,tzinfo=timezone.utc),"LYFT","")
cands = [EmailCandidate("m_a","s","p",datetime(2026,5,5,tzinfo=timezone.utc),"x@y","p"),
         EmailCandidate("m_b","s","p",datetime(2026,5,5,tzinfo=timezone.utc),"x@y","p")]
repo = FakeRepo(txn,
                last_summary={"match_run_id": 50, "status": "succeeded",
                              "model_name": "claude-sonnet-4-5", "prompt_version": PROMPT_VERSION,
                              "candidate_message_ids": ["m_a", "m_b"]},
                active={"match_id": 50, "email_message_id": "m_a", "state": "ai_match_confident",
                        "selected_by": "ai", "ai_confidence": 0.95})
svc = object.__new__(MatchService)
svc._settings = type("S", (), {"mailcart_body_enrichment_enabled": True,
                               "mailcart_body_enrichment_limit": 75, "auto_confirm_threshold": 0.9})()
svc._repository = repo
svc._mailcart_client = FakeClient([cands])
svc._ai_ranker = FakeRanker("claude-sonnet-4-5")
result = svc.match_transaction("txn1")
checks = [
    result.get("skipped") is True,
    result.get("run_id") == 50,
    result.get("selected_message_ids") == ["m_a"],
    repo.create_run_calls == 0,
    svc._mailcart_client.search_calls == 1,
]
print(all(checks))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service runs full AI pipeline when candidate set changes since last run" {
  #R020: Different candidate id set must defeat the cache and trigger a fresh evaluation.
  #R020-T02: Verify the cache miss path creates a run, ranks, calls the AI, and persists.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from datetime import datetime, timezone
from decimal import Decimal
from matchy.ai_ranker import PROMPT_VERSION
from matchy.models import AiSelection, EmailCandidate, TransactionInput
from matchy.service import MatchService

class FakeRepo:
    class Ctx:
        def __init__(self, session): self.session = session
        def __enter__(self): return self.session
        def __exit__(self, *exc): return False
    def __init__(self, txn, last_summary):
        self.txn = txn; self.last_summary = last_summary
        self.created = []; self.persisted_with = None; self.candidates_inserted = None
    def session(self): return FakeRepo.Ctx(_FakeSession())
    def load_transaction(self, session, transaction_id): return self.txn
    def read_last_run_summary(self, session, transaction_id): return self.last_summary
    def read_active_match_summary(self, session, transaction_id): return None
    def create_run(self, **kwargs): self.created.append(kwargs); return 101
    def update_run_model_name(self, **kwargs): pass
    def insert_candidates(self, **kwargs): self.candidates_inserted = kwargs
    def persist_ai_result(self, **kwargs):
        self.persisted_with = kwargs
        return list(kwargs["ai_selection"].selected_message_ids)
    def mark_run_failed(self, *a, **k): pass

class _FakeSession:
    def execute(self, *a, **k):
        class R:
            def mappings(self): return self
            def all(self): return []
        return R()

class FakeClient:
    def __init__(self, results): self._results = results
    def search_candidates(self, query, limit=75): return self._results.pop(0) if self._results else []
    def get_message(self, mid): return {"text_body": "$35.99 fare"}

class FakeRanker:
    def planned_model_name(self): return "claude-sonnet-4-5"
    def select(self, txn, ranked):
        return AiSelection(selected_message_ids=[ranked[0].candidate.message_id], confidence=0.95,
                           uncertain=False, rationale="ok", backend="anthropic", model_name="claude-sonnet-4-5")

txn = TransactionInput("txn1","acc",Decimal("35.99"),datetime(2026,5,5,tzinfo=timezone.utc),"LYFT","")
new_cands = [EmailCandidate("m_new","subj","preview",datetime(2026,5,5,tzinfo=timezone.utc),"x@y","preview")]
repo = FakeRepo(txn, last_summary={"match_run_id": 50, "status": "succeeded",
                                   "model_name": "claude-sonnet-4-5", "prompt_version": PROMPT_VERSION,
                                   "candidate_message_ids": ["m_old"]})
svc = object.__new__(MatchService)
svc._settings = type("S", (), {"mailcart_body_enrichment_enabled": True,
                               "mailcart_body_enrichment_limit": 75, "auto_confirm_threshold": 0.9})()
svc._repository = repo
svc._mailcart_client = FakeClient([new_cands])
svc._ai_ranker = FakeRanker()
result = svc.match_transaction("txn1")
checks = [
    result.get("skipped") is False,
    result["run_id"] == 101,
    result["selected_message_ids"] == ["m_new"],
    len(repo.created) == 1,
    repo.persisted_with is not None,
]
print(all(checks))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service refuses to cache-hit when last run was failed" {
  #R020: Failed runs are never cache-eligible so transient errors self-heal on the next loop.
  #R020-T03: Verify a 'failed' last run forces a fresh evaluation even with the same id set.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from datetime import datetime, timezone
from decimal import Decimal
from matchy.ai_ranker import PROMPT_VERSION
from matchy.models import AiSelection, EmailCandidate, TransactionInput
from matchy.service import MatchService

class FakeRepo:
    class Ctx:
        def __init__(self, session): self.session = session
        def __enter__(self): return self.session
        def __exit__(self, *exc): return False
    def __init__(self, txn, last_summary): self.txn = txn; self.last_summary = last_summary; self.created = 0
    def session(self): return FakeRepo.Ctx(_FakeSession())
    def load_transaction(self, session, transaction_id): return self.txn
    def read_last_run_summary(self, session, transaction_id): return self.last_summary
    def read_active_match_summary(self, session, transaction_id): return None
    def create_run(self, **kwargs): self.created += 1; return 200
    def update_run_model_name(self, **kwargs): pass
    def insert_candidates(self, **kwargs): pass
    def persist_ai_result(self, **kwargs): return list(kwargs["ai_selection"].selected_message_ids)
    def mark_run_failed(self, *a, **k): pass

class _FakeSession:
    def execute(self, *a, **k):
        class R:
            def mappings(self): return self
            def all(self): return []
        return R()

class FakeClient:
    def __init__(self, results): self._results = results
    def search_candidates(self, query, limit=75): return self._results.pop(0) if self._results else []
    def get_message(self, mid): return {}

class FakeRanker:
    def planned_model_name(self): return "claude-sonnet-4-5"
    def select(self, txn, ranked):
        return AiSelection(selected_message_ids=[], confidence=0.0, uncertain=True,
                           rationale="no", backend="anthropic", model_name="claude-sonnet-4-5")

txn = TransactionInput("txn1","acc",Decimal("35.99"),datetime(2026,5,5,tzinfo=timezone.utc),"LYFT","")
cands = [EmailCandidate("m_same","s","p",datetime(2026,5,5,tzinfo=timezone.utc),"x@y","p")]
repo = FakeRepo(txn, last_summary={"match_run_id": 60, "status": "failed",
                                   "model_name": "claude-sonnet-4-5", "prompt_version": PROMPT_VERSION,
                                   "candidate_message_ids": ["m_same"]})
svc = object.__new__(MatchService)
svc._settings = type("S", (), {"mailcart_body_enrichment_enabled": True,
                               "mailcart_body_enrichment_limit": 75, "auto_confirm_threshold": 0.9})()
svc._repository = repo
svc._mailcart_client = FakeClient([cands])
svc._ai_ranker = FakeRanker()
result = svc.match_transaction("txn1")
print(result.get("skipped") is False and repo.created == 1)
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service pending matcher tolerates per-transaction failures" {
  #R025: One transaction's exception must not abort the whole batch.
  #R025-T01: Verify the batch still processes subsequent transactions after a failure.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
import logging
logging.getLogger("matchy.service").setLevel(logging.CRITICAL)
from matchy.service import MatchService

class Repo:
    class Ctx:
        def __enter__(self): return object()
        def __exit__(self, *exc): return False
    def session(self): return Repo.Ctx()
    def list_pending_transaction_ids(self, session, limit=100, lookback_days=14):
        return ["txn_a", "txn_b", "txn_c"]

service = object.__new__(MatchService)
service._repository = Repo()
def flaky_match_transaction(transaction_id, trigger_source="manual"):
    if transaction_id == "txn_b": raise RuntimeError("anthropic 429")
    return {"transaction_id": transaction_id, "selected_message_ids": ["m_" + transaction_id]}
service.match_transaction = flaky_match_transaction
rows = service.match_pending_transactions(limit=3, lookback_days=14, trigger_source="auto")
checks = [
    len(rows) == 3,
    rows[0]["selected_message_ids"] == ["m_txn_a"],
    rows[1].get("error") == "anthropic 429",
    rows[1]["selected_message_ids"] == [],
    rows[2]["selected_message_ids"] == ["m_txn_c"],
]
print(all(checks))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service pending matcher loads pending ids then runs each transaction" {
  #R010: Pending matcher uses repository discovery and runs match_transaction for each pending transaction id.
  #R010-T01: Verify pending list is read once and each transaction id is delegated to match_transaction.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.service import MatchService

class Repo:
    class Ctx:
        def __enter__(self):
            return object()
        def __exit__(self, exc_type, exc, tb):
            return False
    def session(self):
        return Repo.Ctx()
    def list_pending_transaction_ids(self, session, limit=100, lookback_days=14):
        return ["txn_1", "txn_2"]

service = object.__new__(MatchService)
service._repository = Repo()
calls = []
def fake_match_transaction(transaction_id, trigger_source="manual"):
    calls.append((transaction_id, trigger_source))
    return {"transaction_id": transaction_id, "trigger_source": trigger_source}
service.match_transaction = fake_match_transaction
rows = service.match_pending_transactions(limit=9, lookback_days=2, trigger_source="auto")
print(len(rows) == 2 and calls == [("txn_1", "auto"), ("txn_2", "auto")])
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
