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
