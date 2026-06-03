# Architecture

Matchy is the matching engine of the eggnest workspace. It starts from a Teller bank transaction, finds
candidate Outlook emails through Mailcart, ranks them with deterministic scoring plus an AI ranker, and persists
the run, candidates, and match decision back into the Teller database.

The cross-repo system landscape is canonical in the eggnest root [`../Architecture.md`](../Architecture.md);
this document covers matchy's internal architecture. Operator-facing run/test/endpoint instructions live in
[`README.md`](README.md).

> Note: matchy is a nested git repository inside the eggnest workspace. Its numbered `NN_*.sh` scripts are thin
> pointers that source `../runner/config/runbook/matchy.env` and exec the corresponding golden in
> [`../runner/`](../runner/).

## Ownership

- Matchy owns transaction-to-email matching orchestration, deterministic scoring, AI ranking, and the
  match/candidate/run persistence in the `teller.*` schema.
- Matchy owns BM25/TF-IDF-style relevance heuristics and the AI prompt contract (`PROMPT_VERSION`).
- Matchy depends on Mailcart for email candidates (HTTPS) and on the Teller DB for source transactions and
  match persistence (SQL). It does not own either store.

## System Landscape

```text
+---------------------------------------------------------------------------------------------------+
|                                          SYSTEM LANDSCAPE                                          |
|                                                                                                   |
|  +--------------------------------+    HTTP (search/get/move)  +--------------------------------+  |
|  |             MATCHY             | -------------------------> |            MAILCART            |  |
|  | - FastAPI service              | <------------------------- | - Outlook/Graph integration    |  |
|  | - Runs transaction-email match |      message candidates    | - Search/body/move endpoints   |  |
|  | - Combines scoring + AI ranker |                            +--------------------------------+  |
|  | - Writes run/candidate/match   |                                                               |
|  |   records to Teller DB         |                                                               |
|  +---------------+----------------+                                                               |
|                  | SQL read/write                                                                 |
|                  v                                                                                |
|  +----------------------------------------------------------+                                     |
|  |                      TELLER DB                           |                                     |
|  | - Source transactions: teller.transaction               |                                     |
|  | - Run table: teller.transaction_email_match_run          |                                     |
|  | - Candidates: teller.transaction_email_candidate         |                                     |
|  | - Match: teller.transaction_email_match                  |                                     |
|  +----------------------------------------------------------+                                     |
+---------------------------------------------------------------------------------------------------+

TRIGGER FLOW
+-----------------------------+   POST /v1/matchy/runs[/pending]   +----------------------------+
| Caller (manual/auto/retry)  |----------------------------------> | Matchy API                 |
| (operator/driver/job)       |                                    | validates ids + starts run |
+-----------------------------+                                    +----------------------------+
```

## Internal Component Model

```text
+-------------------------------------------------------------------------------+
|                                 MATCHY SERVICE                                |
|                                                                              |
|  create_app() (matchy/api.py)                                                |
|   - GET  /health                                                             |
|   - POST /v1/matchy/runs            (explicit transaction_ids)               |
|   - POST /v1/matchy/runs/pending    (discover + batch)                       |
|   - POST /v1/matchy/confirm         (human override)                         |
|        | lazy MatchService (503 if DB config fails)                          |
|        v                                                                     |
|  MatchService (matchy/service.py)  -- per-transaction pipeline               |
|        |                |                |                                    |
|        v                v                v                                    |
|  MatchRepository    MailcartClient    AiRanker                               |
|  (repository.py)    (mailcart_        (ai_ranker.py)                         |
|  SQLAlchemy text()   client.py)        Anthropic -> OpenAI -> deterministic  |
|        |             requests              |                                  |
|        v                v                  v                                  |
|   Teller Postgres   Mailcart API      rank_candidates (scoring.py)           |
|                                            |                                  |
|                                            v                                  |
|                                       scoring_core.py (pure functions)        |
+-------------------------------------------------------------------------------+
```

| Component | Responsibility |
|-----------|----------------|
| `api.py` | FastAPI factory + Pydantic request/response models; lazily builds `MatchService` |
| `service.py` | Orchestrates the per-transaction pipeline and the pending-batch executor |
| `repository.py` | Raw SQL via SQLAlchemy `text()` against `teller.*` run/candidate/match tables |
| `mailcart_client.py` | HTTPS client for Mailcart search/get/move (TLS, mkcert CA resolution) |
| `scoring.py` / `scoring_core.py` | Deterministic weighted ranker; pure helpers are mutation-tested |
| `ai_ranker.py` | AI selection chain with deterministic fallback; owns `PROMPT_VERSION` |
| `models.py` | Frozen domain types (`TransactionInput`, `EmailCandidate`, `RankedCandidate`, `AiSelection`) |
| `settings.py` | Frozen config resolved via 1psa then `~/.env`; feature flags and timeouts |
| `cldr_cache.py` | Unicode CLDR currency cache + matcher for receipt currency filtering |

## Match Pipeline

`MatchService.match_transaction` runs these steps per transaction:

1. Load the transaction from the Teller DB (raise if missing).
2. Search Mailcart with tiered queries, stopping at the first tier that returns candidates.
3. Optionally enrich candidate bodies via `GET /v1/messages/{id}` (default on, bounded by limit/timeout).
4. Filter candidates by standalone CLDR currency tokens (`CldrCurrencyMatcher`).
5. Cache check: skip the AI call if a prior run used the same model, `PROMPT_VERSION`, and candidate-id set
   (`force_rematch` bypasses).
6. Create a `transaction_email_match_run` row.
7. `rank_candidates` (deterministic) then `AiRanker.select`.
8. `insert_candidates` + `persist_ai_result`, mapping confidence to a match state and run status.

`match_pending_transactions` discovers pending transaction ids in SQL and runs `match_transaction` across a
`ThreadPoolExecutor` (default 4 workers), preserving result order and isolating per-transaction failures.

### Tiered Mailcart search (early-stop)

Up to two search terms (>= 4 chars, counterparty first then description) drive a sequential query plan that
stops at the first non-empty result: `body:term+date` -> `subject:term+date` -> `body:term` (no date) -> `""`
(recency fallback). Transient Mailcart failures trigger a cooldown; per-tier timeouts fall through to the next
tier rather than aborting.

### AI-skip cache

A SHA-256 over the sorted candidate message ids is compared against the last run. The cache hits only when the
prior run shares the same `model_name`, `PROMPT_VERSION`, and a terminal status in
`{succeeded, needs_review, no_candidates}`, returning `skipped: true` with no new AI spend.

## Scoring

`rank_candidates` composes a weighted score (capped at 1.0), sorts descending, and attaches a `reasons` dict:

```text
score = min(1.0,
    merchant_overlap        * 0.30
  + description_overlap     * 0.20
  + amount_hint             * 0.15
  + compact_merchant_hint   * 0.20
  + sender_hint             * 0.10
  + time_proximity          * 0.20
  + unmatched_email_bonus (0.15 if candidate not already matched))
```

`scoring_core.py` holds the pure helpers (normalization, token overlap, amount-in-text in cents, sender hint,
compact merchant, time-proximity buckets) and is the mutmut mutation-testing target (90% gate).

## AI Ranker

`AiRanker.select` tries Anthropic (primary), then OpenAI (fallback), then a deterministic top-score selection.
It sends a JSON-only prompt with the top candidates and body excerpts, and shrinks/retries on Anthropic rate
limits. `PROMPT_VERSION` (currently `v3`) participates in cache invalidation. Confidence is compared against
`MATCHY_AUTO_CONFIRM_THRESHOLD` (default 0.90) to decide `ai_match_confident` vs `ai_candidate_uncertain`.

## Persistence

`MatchRepository` reads and writes `teller.*` tables with raw SQL:

| Table | Role |
|-------|------|
| `teller.transaction` | Source transactions |
| `teller.transaction_email_match_run` | Run metadata, status, model, prompt version |
| `teller.transaction_email_candidate` | Scored candidates + cached subject/sender/snippet |
| `teller.transaction_email_match` | Active match state per transaction |

Run statuses: `needs_review`, `succeeded`, `no_candidates`, `failed`. Match states include
`ai_match_confident`, `ai_candidate_uncertain`, `ai_no_match_found`, `human_confirmed`. "Pending" work is
transactions in the lookback window without a settled active match (re-queues uncertain and AI-declared
no-match states, but not human-settled states).

## Engine-Level Tests vs Live Service

Two verification layers exist:

- Live service: `tests/py/` (pytest, FastAPI `TestClient`) exercises the API, service, repository, scoring, AI
  ranker, and Mailcart client with stubs.
- Engine-level: curated `cases/` are run offline against `rank_candidates` plus a replayed `AiSelection` (no DB,
  Mailcart, or Graph). The canonical harness for these cases lives at the eggnest workspace root
  (`../tests/harness/`, `../tests/test_e2e_cases.py`). See [`cases/README.md`](cases/README.md).

## Languages, Frameworks, and Tooling

| Concern | Stack |
|---------|-------|
| Application | Python 3.10+ |
| HTTP API | FastAPI, Pydantic, Uvicorn, Starlette |
| DB access | SQLAlchemy 2.x, psycopg2-binary (PostgreSQL `teller` schema) |
| Email client | requests (Mailcart HTTPS) |
| AI | anthropic, openai (optional; deterministic fallback) |
| Tests | pytest, Hypothesis (properties + fuzz), mutmut (mutation), Bats (shell contracts) |
| Static analysis | ruff, bandit, semgrep, gitleaks, detect-secrets, pip-audit, shellcheck (runner lanes) |
| Packaging | setuptools (`pyproject.toml`) |
| Secrets | 1psa CLI + `~/.env` fallback |

Quality lanes (`05` unit, `06` security, `07` AV, `10` mutation, `11` fuzz, `12` parallel batch, `tNN_*`
lanes) are runner pointers configured by `../runner/config/runbook/matchy.env`. There is no Makefile or Docker;
all setup is via the numbered runbook scripts.
