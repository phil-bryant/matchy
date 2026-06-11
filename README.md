# matchy

Matchy starts from Teller transactions and finds candidate Outlook emails, then stores AI-assisted match decisions in Teller DB.

## Pre-release CI/CD Policy

CI is **implemented but intentionally disabled for automatic runs** until the `v1.0` customer release. A GitHub
Actions workflow exists at `.github/workflows/ci.yml`, but it is **manual-dispatch-only**
(`on: workflow_dispatch`) — it does **not** trigger on `push`, `pull_request`, or `schedule`. Pre-release, the
enforcement mechanism is the local numbered test lanes (`tests/tNN_*.sh` + `./05_run_all_tests_parallel.sh`),
not GitHub-hosted CI: this is a solo project and red X's on every push are noise rather than signal. matchy is
pure-Python FastAPI, so the workflow runs a high-coverage Linux-portable subset (code quality `t00` + Python
unit `t06` + requirements traceability `t04`, delegating to the shared `runner` goldens); the AV (`t01`),
dependency-freshness (`t02`), SAST (`t04`), shell/Bats (`t05`), mutation (`t08`), fuzz (`t08`), DAST (`t09`),
and FileVault (`t10`) lanes stay local. It is kept correct and manually runnable so it can be wired to
`push`/`pull_request` as the project approaches `v1.0`. This matches the workspace-wide policy in
[`teller`'s README](../teller/README.md#pre-release-cicd-policy).

## Run

1. Install dependencies:
   - `python3 -m pip install -e .`
2. Set required environment variables:
   - Teller DB config resolves in strict order: `1psa` first, `~/.env` fallback, otherwise startup error.
   - Default 1psa item: `localhost_postgres_teller` (override: `TELLER_DB_PASSWORD_1PSA_REF`).
   - 1psa item must provide: `username`, `password`, `host`, `port`, `database`.
   - `~/.env` fallback supports the same keys (`username`, `password`, `host`, `port`, `database`) or mapped keys (`TELLER_DB_USER`, `TELLER_DB_PASSWORD`, `TELLER_DB_HOST`, `TELLER_DB_PORT`, `TELLER_DB_NAME`).
   - `MAILCART_SERVICE_BASE_URL` (must be HTTPS, for example `https://127.0.0.1:8788`)
   - `MAILCART_SERVICE_TOKEN` (optional if Mailcart is running without auth)
  - `MATCHY_API_AUTH_TOKEN` (optional for local script runs; defaults to `matchy-local-dev-token` in `./05` + `./06`)
   - Optional TLS verify override: `MATCHY_MAILCART_CA_BUNDLE` (path to a CA/cert bundle trusted for Mailcart TLS).
   - Optional startup preflight controls:
     - `MATCHY_MAILCART_STARTUP_HEALTHCHECK` (`true`/`false`, default `true`)
     - `MATCHY_MAILCART_STARTUP_HEALTHCHECK_TIMEOUT_SECONDS` (default `2`)
   - AI keys for the match ranker are resolved via `1psa` with Anthropic primary and OpenAI fallback:
     - `anthropic_api_key` (default 1psa item; override `MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM`; env override `ANTHROPIC_API_KEY`)
     - `openai_api_key` (default 1psa item; override `MATCHY_OPENAI_API_KEY_1PSA_ITEM`; env override `OPENAI_API_KEY`)
     - If neither is available, Matchy falls back to deterministic scoring only.
3. Start API:
  - `./06_run_matchy_api.py`
  - `./06_run_matchy_api.py --profile` (enable startup timing/profiling logs)
   - Options are available as CLI args (for example `--mailcart-body-enrichment-limit`, `--mailcart-body-enrichment-timeout-seconds`, `--mailcart-get-message-timeout-seconds`, `--pending-max-workers`) so local runs do not require env-var-only control.
4. Run driver:
  - `./07_run_matchy_driver.py --once`
  - `./07_run_matchy_driver.py --profile` (startup + in-flight request heartbeat logs every 5s while waiting)

## Test

Run unit tests (pytest for application modules, then Bats for numbered shell scripts in parallel by file; set `BATS_JOBS` or `BATS_USE_NATIVE_JOBS=true` to tune concurrency):

```bash
./02_create_venv.sh
activate
./03_prepare_supply_chain_integrity.sh
./04_load_requirements.sh
./05_run_unit_tests.sh
./11_run_fuzz.sh
./10_run_mutation_tests.sh   # mutmut on scoring_core + models; 90% score gate
```

`11` runs Hypothesis property tests on scoring invariants (semantic bucket/normalization checks plus bounded invariants). `10` runs real mutmut mutation testing against `tests/py/test_scoring_core.py` (direct scoring contracts), `test_scoring.py`, and `test_models.py` with Hypothesis disabled for speed. The default mutation score gate is **90%**. On macOS, `10` uses a subprocess pytest driver (`tools/mutmut_darwin.py`) because stock mutmut forks after threaded pytest and every mutant SIGSEGVs. On Linux, `10` uses `mutmut run` directly. Override with `MUTATION_USE_SUBPROCESS=false` (mac) or `true` (linux) if needed.

Run all CI gate scripts in parallel (completion-order PASS/FAIL lines on the terminal; full output per script in `.parallel-checks-reports/<script-stem>.log`):

```bash
./05_run_all_tests_parallel.sh
```

Excluded from the parallel batch: setup scripts (`01`–`04`) and integration entrypoints (`06_run_matchy_api.py`, `07_run_matchy_driver.py`).

Use `./08_clean_generated_files.sh` to clear generated artifacts between runs (moves outputs to `~/.Trash`).

## Endpoint

- Auth header for mutating endpoints:
  - `Authorization: Bearer $MATCHY_API_AUTH_TOKEN`
- `POST /v1/matchy/runs`
  - Body:
    - `{"transaction_ids": ["txn_1"], "trigger_source": "manual"}`
- `POST /v1/matchy/runs/pending`
  - Body:
    - `{"limit": 100, "lookback_days": 14, "trigger_source": "auto"}`
  - Purpose:
    - Driver-friendly endpoint that discovers active-unmatched transactions and runs matching in batch.
  - Driver default batch size is `10` per run (`./07_run_matchy_driver.py`), with CLI arg overrides (`--limit`, `--timeout-seconds`, `--once`, etc.).
- `POST /v1/matchy/confirm`
  - Body:
    - `{"transaction_id": "txn_1", "email_message_id": "msg_1", "note": "optional"}`

## GLOBAL ARCHITECTURE: TELLER → MATCHY ← MAILCART
```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            SYSTEM LANDSCAPE                                           │
│                                                                                                       │
│  ┌────────────────────────────────┐      HTTPS (search/move)      ┌────────────────────────────────┐  │
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
│  │ - Match run table: `matchy.transaction_email_match_run`  │                                         │
│  │ - Candidates table: `matchy.transaction_email_candidate` │                                         │
│  │ - Match table: `matchy.transaction_email_match`          │                                         │
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
