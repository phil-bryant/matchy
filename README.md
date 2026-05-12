# matchy

Matchy starts from Teller transactions and finds candidate Outlook emails, then stores AI-assisted match decisions in Teller DB.

## Run

1. Install dependencies:
   - `python3 -m pip install -e .`
2. Set required environment variables:
   - `TELLER_DB_PASSWORD`
   - `EMAIL_SERVICE_BASE_URL`
   - `OPENAI_API_KEY` (optional; fallback deterministic mode if unset)
3. Start API:
   - `python3 01_run_matchy_api.py`

## Endpoint

- `POST /v1/matchy/runs`
  - Body:
    - `{"transaction_ids": ["txn_1"], "trigger_source": "manual"}`
