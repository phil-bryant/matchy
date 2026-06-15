#!/usr/bin/env python3
"""Python/C++ oracle parity harness for the matchy core migration (M6).

For every scenario in scenarios.json this harness runs the named deterministic
op through BOTH implementations and diffs the normalized JSON results:

  * Python reference: matchy.scoring / matchy.caching / matchy.near_duplicate /
    matchy.cldr_cache (the production modules, imported directly).
  * C++ core:         matchy_oracle_runner <op> @payload.json

Only matchy's side-effect-free logic is covered here (scoring + candidate-set
hashing, near-duplicate collapse, SimHash, CLDR currency matching). The DB,
Mailcart HTTP, and AI layers are integration-bound and are exercised by their
own lanes, not by byte-for-byte parity.

Usage (from the matchy repo, using the matchy venv interpreter):
  matchy-venv/bin/python3 src/core/oracle/compare_oracle.py \
    --runner src/core/build/matchy_oracle_runner
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = ORACLE_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# End-to-end parity (DB + Mailcart + AI) uses a seeded SQLCipher fixture matching the C++
# testfx::Fixture seed, the same teller sqlite DDL the C++ oracle runner compiles against, and
# a fixed SQLCipher key. run_id/match_id are DB-generated and normalized out before diffing.
E2E_OPS_SET = {"match_transaction", "match_pending", "confirm"}
E2E_SQLCIPHER_KEY = "matchycore-test-key"
E2E_NORMALIZED_ID_KEYS = {"run_id", "match_id"}
TELLER_SQLITE_DDL = REPO_ROOT.parent / "teller" / "src" / "sql" / "sqlite" / "create_database.sql"

# Bare-name seed mirroring src/core/tests/fixture.hpp (applied directly to the file, which matchy
# later ATTACHes as the `teller` schema). Keeps txn-1/txn-2 identical across both engines.
E2E_SEED_SQL = """
INSERT INTO institution (institution_id, name) VALUES ('inst-1', 'Test Bank');
INSERT INTO account_links (self_link) VALUES ('https://example/accounts/a1');
INSERT INTO account (currency, enrollment_id, account_id, institution_id, last_four,
                     account_links_id, name, type, subtype, status)
VALUES ('USD', 'enr-1', 'acct-1', 'inst-1', '0001', 1, 'Checking', 'depository', 'checking', 'open');
INSERT INTO transaction_type (code) VALUES ('card_payment');
INSERT INTO transaction_details_counterparty (name, type) VALUES ('Blue Bottle Coffee', 'organization');
INSERT INTO transaction_details (processing_status, category, transaction_details_counterparty_id)
VALUES ('complete', 'dining', 1);
INSERT INTO transaction_links (self_link, account) VALUES ('https://example/txn/t1', 'acct-1');
INSERT INTO "transaction" (account_id, amount, date, description, transaction_details_id, status,
                           transaction_id, transaction_links_id, transaction_type_id)
VALUES ('acct-1', -1050, '2024-06-01', 'BLUE BOTTLE COFFEE purchase', 1, 'posted', 'txn-1', 1, 1);
INSERT INTO transaction_details (processing_status, category) VALUES ('complete', 'misc');
INSERT INTO transaction_links (self_link, account) VALUES ('https://example/txn/t2', 'acct-1');
INSERT INTO "transaction" (account_id, amount, date, description, transaction_details_id, status,
                           transaction_id, transaction_links_id, transaction_type_id)
VALUES ('acct-1', -2030, '2024-06-02', 'CLOUD HOSTING LLC subscription', 2, 'posted', 'txn-2', 2, 1);
"""

# Settings env shared by both engines: deterministic AI (no keys), no enrichment/move/currency/network.
E2E_SETTINGS_ENV = {
    "MATCHY_WRITE_ENABLED": "true",
    "MATCHY_MAILCART_BODY_ENRICHMENT": "false",
    "MATCHY_MAILCART_STARTUP_HEALTHCHECK": "false",
    "MATCHY_EMAIL_MOVE_ENABLED": "false",
    "MATCHY_NEAR_DUPLICATE_MAX_HAMMING_DISTANCE": "0",
    "MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED": "false",
    "MATCHY_PENDING_MAX_WORKERS": "1",
    "ANTHROPIC_API_KEY": "",
    "OPENAI_API_KEY": "",
    "ONEPSA_LIB_PATH": "/nonexistent-oracle-onepsa.dylib",
}

# Round all floats to this many decimals before comparing so JSON float
# serialization differences between Python and nlohmann/json are not parity
# failures; the candidate-set hash (computed identically on both sides via a
# "%0.8f" score normalization) is the exact end-to-end check.
FLOAT_PRECISION = 6


#R001: Matchycore traceability implementation coverage.
def parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    # Mailcart-sourced candidate times are tz-aware UTC in production; the C++ core's
    # FormatIsoUtc always emits a "+00:00" offset, so attach UTC to naive scenario
    # inputs to keep email_received_at (and thus the candidate-set hash) identical.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


#R001: Matchycore traceability implementation coverage.
def build_transaction(payload: dict):
    from matchy.models import TransactionInput

    return TransactionInput(
        transaction_id=payload.get("transaction_id", ""),
        account_id=payload.get("account_id", ""),
        amount=Decimal(str(payload.get("amount", "0"))),
        date=parse_datetime(payload.get("date", "1970-01-01T00:00:00")),
        description=payload.get("description", ""),
        counterparty_name=payload.get("counterparty_name", ""),
    )


#R001: Matchycore traceability implementation coverage.
def build_candidate(payload: dict):
    from matchy.models import EmailCandidate

    return EmailCandidate(
        message_id=payload.get("message_id", ""),
        subject=payload.get("subject", ""),
        preview=payload.get("preview", ""),
        received_at=parse_datetime(payload.get("received_at", "1970-01-01T00:00:00")),
        sender=payload.get("sender", ""),
        body_text=payload.get("body_text", ""),
    )


#R001: Matchycore traceability implementation coverage.
def python_rank(payload: dict) -> dict:
    from matchy.caching import CachingMixin
    from matchy.scoring import rank_candidates

    transaction = build_transaction(payload.get("transaction", {}))
    candidates = [build_candidate(item) for item in payload.get("candidates", [])]
    already_matched = set(payload.get("already_matched_ids", []))
    ranked = rank_candidates(transaction, candidates, already_matched)
    cache_rows = CachingMixin._ranked_candidate_cache_rows(None, ranked)
    message_ids = [str(row["email_message_id"]) for row in cache_rows]
    ranked_rows = [
        {"email_message_id": row.candidate.message_id, "score": row.score, "reasons": row.reasons}
        for row in ranked
    ]
    return {
        "ranked": ranked_rows,
        "candidate_set_hash": CachingMixin._candidate_set_hash(cache_rows),
        "candidate_message_id_hash": CachingMixin._candidate_message_id_hash(message_ids),
    }


#R001: Matchycore traceability implementation coverage.
def python_collapse(payload: dict) -> dict:
    from matchy.near_duplicate import NearDuplicateMixin

    candidates = [build_candidate(item) for item in payload.get("candidates", [])]
    kept = NearDuplicateMixin._collapse_near_duplicates(candidates, int(payload.get("max_distance", 0)))
    return {"kept_message_ids": [candidate.message_id for candidate in kept]}


#R001: Matchycore traceability implementation coverage.
def python_simhash(payload: dict) -> dict:
    from matchy.near_duplicate import _simhash64

    return {"fingerprint": str(_simhash64(payload.get("text", "")))}


#R001: Matchycore traceability implementation coverage.
def python_cldr_tokens(payload: dict) -> dict:
    from matchy.cldr_cache import CldrCurrenciesCache

    tokens = CldrCurrenciesCache.parse_currency_tokens(payload.get("payload", {}))
    return {"tokens": sorted(tokens)}


#R001: Matchycore traceability implementation coverage.
def python_cldr_match(payload: dict) -> dict:
    from matchy.cldr_cache import CldrCurrencyMatcher

    matcher = CldrCurrencyMatcher(frozenset(payload.get("tokens", [])))
    return {"contains": matcher.contains_standalone_currency(payload.get("text", ""))}


PYTHON_OPS = {
    "rank": python_rank,
    "collapse": python_collapse,
    "simhash": python_simhash,
    "cldr_tokens": python_cldr_tokens,
    "cldr_match": python_cldr_match,
}


#R001: In-memory Mailcart double replaying scenario candidates for end-to-end DB parity ops.
class _FakeMailcart:
    #R001: Capture the recorded candidate list for replay across every search query.
    def __init__(self, candidates: list):
        self._candidates = candidates

    #R001: Replay the recorded candidate list regardless of the query plan tier.
    def search_candidates(self, query: str = "", limit: int = 0) -> list:
        return list(self._candidates)

    #R001: Enrichment is disabled in parity scenarios; return an empty payload.
    def get_message(self, message_id: str, timeout_seconds: int = 0) -> dict:
        return {}

    #R001: Record the move target and report success without external I/O.
    def move_to_matchy(self, message_id: str) -> bool:
        return True


#R001: Seed a fresh SQLCipher fixture file matching the C++ testfx::Fixture seed.
def _bootstrap_sqlite_db(db_path: str) -> None:
    from pysqlcipher3 import dbapi2 as sqlcipher

    ddl_text = TELLER_SQLITE_DDL.read_text(encoding="utf-8")
    connection = sqlcipher.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(f"PRAGMA key = '{E2E_SQLCIPHER_KEY}'")
        cursor.executescript(ddl_text)
        cursor.executescript(E2E_SEED_SQL)
        connection.commit()
    finally:
        connection.close()


#R001: Install the shared deterministic parity env (sqlite profile, no AI keys, no network).
def _install_e2e_env(tmp: Path) -> None:
    profile_file = tmp / "db-profiles.json"
    profile_file.write_text(
        json.dumps({"default_profile": "sqlite", "profiles": {"sqlite": {"1psa_or_env_item": "oracle_sqlite"}}}),
        encoding="utf-8",
    )
    os.environ.update(E2E_SETTINGS_ENV)
    os.environ["TELLER_DB_PROFILE_FILE"] = str(profile_file)
    os.environ["TELLER_DB_PROFILE"] = "sqlite"
    os.environ["TELLER_DB_SQLCIPHER_KEY"] = E2E_SQLCIPHER_KEY
    os.environ["TELLER_DB_SQLITE_PATH"] = str(tmp / "placeholder.sqlite3")


#R001: Point matchy at a fresh seeded sqlite file and drop the cached teller engine.
def _rebind_sqlite_db(db_path: str) -> None:
    import teller.teller_db as teller_db
    from teller.teller_db_profile import reset_profile_cache

    _bootstrap_sqlite_db(db_path)
    os.environ["TELLER_DB_SQLITE_PATH"] = db_path
    teller_db._engine = None
    reset_profile_cache()


#R001: Build a Python MatchService bound to the seeded sqlite fixture with stubbed Mailcart/AI.
def _build_python_service(payload: dict):
    from matchy.ai_ranker import AiRanker
    from matchy.cldr_cache import CldrCurrencyMatcher
    from matchy.repository import MatchRepository
    from matchy.service import MatchService
    from matchy.settings import Settings

    settings = Settings()
    ai_ranker = AiRanker(settings)
    ai_ranker._anthropic_client = None
    ai_ranker._openai_client = None
    mailcart = _FakeMailcart([build_candidate(item) for item in payload.get("candidates", [])])
    return MatchService(
        settings,
        repository=MatchRepository(settings),
        mailcart_client=mailcart,
        ai_ranker=ai_ranker,
        cldr_currency_matcher=CldrCurrencyMatcher(frozenset()),
    )


#R001: Drive one transaction end-to-end through the Python service for parity diffing.
def python_match_transaction(payload: dict) -> dict:
    service = _build_python_service(payload)
    return service.match_transaction(
        transaction_id=payload.get("transaction_id", ""),
        trigger_source=payload.get("trigger_source", "manual"),
        force_rematch=payload.get("force_rematch", False),
    )


#R001: Drive the pending batch end-to-end through the Python service for parity diffing.
def python_match_pending(payload: dict) -> dict:
    service = _build_python_service(payload)
    rows = service.match_pending_transactions(
        limit=payload.get("limit", 100),
        lookback_days=payload.get("lookback_days", 3650),
        trigger_source=payload.get("trigger_source", "auto"),
        force_rematch=payload.get("force_rematch", False),
    )
    return {"results": rows}


#R001: Drive a human confirm end-to-end through the Python service for parity diffing.
def python_confirm(payload: dict) -> dict:
    service = _build_python_service(payload)
    return service.confirm_match(
        transaction_id=payload.get("transaction_id", ""),
        email_message_id=payload.get("email_message_id", ""),
        note=payload.get("note"),
    )


E2E_PYTHON_OPS = {
    "match_transaction": python_match_transaction,
    "match_pending": python_match_pending,
    "confirm": python_confirm,
}


#R001: Matchycore traceability implementation coverage.
def normalize(value):
    result = value
    if isinstance(value, float):
        result = round(value, FLOAT_PRECISION)
    elif isinstance(value, dict):
        result = {
            key: ("<id>" if key in E2E_NORMALIZED_ID_KEYS and item is not None else normalize(item))
            for key, item in value.items()
        }
    elif isinstance(value, list):
        result = [normalize(item) for item in value]
    return result


#R001: Matchycore traceability implementation coverage.
def run_runner(runner: Path, op: str, payload: dict, tmp: Path) -> dict:
    payload_file = tmp / "payload.json"
    payload_file.write_text(json.dumps(payload))
    completed = subprocess.run(
        [str(runner), op, "@" + str(payload_file)], capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise RuntimeError(f"runner failed: {completed.stdout.strip()} {completed.stderr.strip()}")
    return json.loads(completed.stdout)


#R001: Diff one scenario set (deterministic or end-to-end) and report per-scenario pass/fail.
def _run_scenario_set(runner: Path, scenarios: list, tmp: Path, e2e: bool) -> int:
    failures = 0
    ops = E2E_PYTHON_OPS if e2e else PYTHON_OPS
    for index, scenario in enumerate(scenarios):
        name = scenario["name"]
        op = scenario["op"]
        payload = scenario["payload"]
        try:
            if e2e:
                _rebind_sqlite_db(str(tmp / f"e2e-{index}.sqlite3"))
            python_result = normalize(ops[op](payload))
            cpp_result = normalize(run_runner(runner, op, payload, tmp))
            matched = python_result == cpp_result
        except Exception as exc:  # harness/runner failure is a parity failure
            matched = False
            python_result = {"harness_error": str(exc)}
            cpp_result = {}
        if matched:
            print(f"ok   {name} [{op}]")
        else:
            failures += 1
            print(f"FAIL {name} [{op}]")
            print(f"  python: {json.dumps(python_result, sort_keys=True)}")
            print(f"  c++   : {json.dumps(cpp_result, sort_keys=True)}")
    return failures


#R001: Matchycore traceability implementation coverage.
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True, help="path to matchy_oracle_runner")
    parser.add_argument("--scenarios", default=str(ORACLE_DIR / "scenarios.json"))
    parser.add_argument("--e2e-scenarios", default=str(ORACLE_DIR / "scenarios_e2e.json"))
    args = parser.parse_args()

    runner = Path(args.runner).resolve()
    exit_code = 0
    if not runner.is_file():
        print(f"oracle runner not found: {runner}", file=sys.stderr)
        exit_code = 2
    else:
        scenarios = json.loads(Path(args.scenarios).read_text())["scenarios"]
        e2e_path = Path(args.e2e_scenarios)
        e2e_scenarios = json.loads(e2e_path.read_text())["scenarios"] if e2e_path.is_file() else []
        total = len(scenarios) + len(e2e_scenarios)
        print(f"Oracle parity: {len(scenarios)} deterministic + {len(e2e_scenarios)} end-to-end scenarios")
        with tempfile.TemporaryDirectory(prefix="matchy-oracle-") as tmp_str:
            tmp = Path(tmp_str)
            _install_e2e_env(tmp)
            failures = _run_scenario_set(runner, scenarios, tmp, e2e=False)
            failures += _run_scenario_set(runner, e2e_scenarios, tmp, e2e=True)
        print(f"\n{total - failures}/{total} scenarios matched")
        if failures:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
