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

# Round all floats to this many decimals before comparing so JSON float
# serialization differences between Python and nlohmann/json are not parity
# failures; the candidate-set hash (computed identically on both sides via a
# "%0.8f" score normalization) is the exact end-to-end check.
FLOAT_PRECISION = 6


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


def python_collapse(payload: dict) -> dict:
    from matchy.near_duplicate import NearDuplicateMixin

    candidates = [build_candidate(item) for item in payload.get("candidates", [])]
    kept = NearDuplicateMixin._collapse_near_duplicates(candidates, int(payload.get("max_distance", 0)))
    return {"kept_message_ids": [candidate.message_id for candidate in kept]}


def python_simhash(payload: dict) -> dict:
    from matchy.near_duplicate import _simhash64

    return {"fingerprint": str(_simhash64(payload.get("text", "")))}


def python_cldr_tokens(payload: dict) -> dict:
    from matchy.cldr_cache import CldrCurrenciesCache

    tokens = CldrCurrenciesCache.parse_currency_tokens(payload.get("payload", {}))
    return {"tokens": sorted(tokens)}


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


def normalize(value):
    result = value
    if isinstance(value, float):
        result = round(value, FLOAT_PRECISION)
    elif isinstance(value, dict):
        result = {key: normalize(item) for key, item in value.items()}
    elif isinstance(value, list):
        result = [normalize(item) for item in value]
    return result


def run_runner(runner: Path, op: str, payload: dict, tmp: Path) -> dict:
    payload_file = tmp / "payload.json"
    payload_file.write_text(json.dumps(payload))
    completed = subprocess.run(
        [str(runner), op, "@" + str(payload_file)], capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise RuntimeError(f"runner failed: {completed.stdout.strip()} {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True, help="path to matchy_oracle_runner")
    parser.add_argument("--scenarios", default=str(ORACLE_DIR / "scenarios.json"))
    args = parser.parse_args()

    runner = Path(args.runner).resolve()
    exit_code = 0
    if not runner.is_file():
        print(f"oracle runner not found: {runner}", file=sys.stderr)
        exit_code = 2
    else:
        scenarios = json.loads(Path(args.scenarios).read_text())["scenarios"]
        failures = 0
        print(f"Oracle parity: {len(scenarios)} scenarios")
        with tempfile.TemporaryDirectory(prefix="matchy-oracle-") as tmp_str:
            tmp = Path(tmp_str)
            for scenario in scenarios:
                name = scenario["name"]
                op = scenario["op"]
                payload = scenario["payload"]
                try:
                    python_result = normalize(PYTHON_OPS[op](payload))
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
        print(f"\n{len(scenarios) - failures}/{len(scenarios)} scenarios matched")
        if failures:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
