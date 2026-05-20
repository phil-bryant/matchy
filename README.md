# matchy

Matchy starts from Teller transactions and finds candidate Outlook emails, then stores AI-assisted match decisions in Teller DB.

## Run

1. Install dependencies:
   - `python3 -m pip install -e .`
2. Set required environment variables:
   - Teller DB password is resolved via `1psa` (default item: `localhost_postgres_teller`; optional override: `TELLER_DB_PASSWORD_1PSA_REF`)
   - `MAILCART_SERVICE_BASE_URL`
   - `MAILCART_SERVICE_TOKEN` (optional if Mailcart is running without auth)
   - AI keys for the match ranker are resolved via `1psa` with Anthropic primary and OpenAI fallback:
     - `anthropic_api_key` (default 1psa item; override `MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM`; env override `ANTHROPIC_API_KEY`)
     - `openai_api_key` (default 1psa item; override `MATCHY_OPENAI_API_KEY_1PSA_ITEM`; env override `OPENAI_API_KEY`)
     - If neither is available, Matchy falls back to deterministic scoring only.
3. Start API:
   - `./08_run_matchy_api.py`

## Test

Run unit tests (pytest for application modules, then Bats for numbered shell scripts in parallel by file; set `BATS_JOBS` or `BATS_USE_NATIVE_JOBS=true` to tune concurrency):

```bash
./02_create_venv.sh
activate
./03_load_requirements.sh
./05_run_unit_tests.sh
./11_run_fuzz.sh
./10_run_mutation_tests.sh   # mutmut on scoring_core + models; 90% score gate
```

`11` runs Hypothesis property tests on scoring invariants (semantic bucket/normalization checks plus bounded invariants). `10` runs real mutmut mutation testing against `tests/py/test_scoring_core.py` (direct scoring contracts), `test_scoring.py`, and `test_models.py` with Hypothesis disabled for speed. The default mutation score gate is **90%**. On macOS, `10` uses a subprocess pytest driver (`tools/mutmut_darwin.py`) because stock mutmut forks after threaded pytest and every mutant SIGSEGVs. On Linux, `10` uses `mutmut run` directly. Override with `MUTATION_USE_SUBPROCESS=false` (mac) or `true` (linux) if needed.

Run all seven CI gate scripts in parallel (completion-order PASS/FAIL lines on the terminal; full output per script in `.parallel-checks-reports/<script-stem>.log`):

```bash
./12_run_all_checks_parallel.sh
```

Excluded from the parallel batch: setup scripts (`01`–`03`) and integration entrypoints (`08_run_matchy_api.py`, `09_run_matchy_driver.py`).

## Endpoint

- `POST /v1/matchy/runs`
  - Body:
    - `{"transaction_ids": ["txn_1"], "trigger_source": "manual"}`
- `POST /v1/matchy/runs/pending`
  - Body:
    - `{"limit": 100, "lookback_days": 14, "trigger_source": "auto"}`
  - Purpose:
    - Driver-friendly endpoint that discovers active-unmatched transactions and runs matching in batch.

## GLOBAL ARCHITECTURE: TELLER → MATCHY ← MAILCART
```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            SYSTEM LANDSCAPE                                           │
│                                                                                                       │
│  ┌────────────────────────────────┐      HTTP (search/move)       ┌────────────────────────────────┐  │
│  │             MATCHY             │ ────────────────────────────► │            MAILCART            │  │
│  │                                │ ◄──────────────────────────── │                                │  │
│  │ - FastAPI service              │        message candidates     │ - Outlook/Graph integration    │  │
│  │ - Runs transaction↔email match │                               │ - Search endpoint for emails   │  │
│  │ - Combines scoring + AI ranker │                               │ - Move endpoint to folder      │  │
│  │ - Writes run/candidate/match   │                               │   `matchy`                     │  │
│  │   records to Teller DB         │                               └────────────────────────────────┘  │
│  └───────────────┬────────────────┘                                                                   │
│                  │ SQL read/write                                                                     │
│                  ▼                                                                                    │
│  ┌──────────────────────────────────────────────────────────┐                                         │
│  │                      TELLER DB                           │                                         │
│  │                                                          │                                         │
│  │ - Source transactions: `teller.transaction`              │                                         │
│  │ - Match run table: `teller.transaction_email_match_run`  │                                         │
│  │ - Candidates table: `teller.transaction_email_candidate` │                                         │
│  │ - Match table: `teller.transaction_email_match`          │                                         │
│  └──────────────────────────────────────────────────────────┘                                         │
│                                                                                                       │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘

TRIGGER FLOW
┌─────────────────────────────┐      POST /v1/matchy/runs       ┌────────────────────────────┐
│ Caller (manual/auto/retry)  │───────────────────────────────► │ Matchy API                 │
│ (operator/job in ecosystem) │                                 │ validates ids + starts run │
└─────────────────────────────┘                                 └────────────────────────────┘
```
## MATCHY INTERNAL ARCHITECTURE
```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                      MATCHY SERVICE                                 │
│                                                                                     │
│  ┌──────────────────────────────────┐                                               │
│  │ FastAPI (`matchy/api.py`)        │                                               │
│  │ - POST /v1/matchy/runs           │                                               │
│  │ - Builds/uses MatchService       │                                               │
│  └──────────────────┬───────────────┘                                               │
│                     │ for each transaction_id                                       │
│                     ▼                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐          │
│  │ MatchService (`matchy/service.py`)                                    │          │
│  │                                                                       │          │
│  │ 1) load_transaction()                                                 │          │
│  │ 2) create_run(status=needs_review)                                    │          │
│  │ 3) build query from description/counterparty                          │          │
│  │ 4) search candidates in Mailcart                                      │          │
│  │ 5) rank_candidates() deterministic scoring                            │          │
│  │ 6) AiRanker.select() (Anthropic → OpenAI → deterministic fallback)    │          │
│  │ 7) insert_candidates() + persist_ai_result()                          │          │
│  │ 8) mark run status: succeeded / needs_review / no_candidates / failed │          │
│  └──────────────────┬────────────────────────────────────────────────────┘          │
│                     │                                                               │
│                     ▼                                                               │
│      ┌──────────────────────────────────┬───────────────────────────┐               │
│      ▼                                  ▼                           ▼               │
│  ┌────────────────────────┐  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ MatchRepository        │  │ rank_candidates     │  │ AiRanker                 │  │
│  │ (`repository.py`)      │  │ (`scoring.py`)      │  │ (`ai_ranker.py`)         │  │
│  │ - SQLAlchemy session   │  │ - token overlap     │  │ - Anthropic Claude JSON  │  │
│  │ - read transaction     │  │ - amount hint score │  │   selection (primary)    │  │
│  │ - write run/candidate/ │  │ - time proximity    │  │ - OpenAI JSON fallback   │  │
│  │   match tables         │  │ - unmatched bonus   │  │ - deterministic last     │  │
│  │                        │  │                     │  │   resort + rationale     │  │
│  └──────────────┬─────────┘  └─────────────────────┘  └──────────────────────────┘  │
│                 │                                                                   │
│                 ▼                                                                   │
│  ┌────────────────────────────────┐                                                 │
│  │ MailcartClient (`mailcart_     │                                                 │
│  │ client.py`)                    │                                                 │
│  │ - GET /v1/messages/search      │                                                 │
│  │ - POST /v1/messages/{id}/move  │                                                 │
│  │   {"folder_name":"matchy"}     │                                                 │
│  └────────────────────────────────┘                                                 │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

DEPENDENCY BOUNDARIES
┌───────────────────────────────────┐        ┌───────────────────────────────────┐
│ External: Mailcart HTTP API       │        │ External: Teller Postgres         │
│ - query/search message candidates │        │ - transaction source rows         │
│ - optional move-to-matchy action  │        │ - run/candidate/match persistence │
└───────────────────────────────────┘        └───────────────────────────────────┘
```
