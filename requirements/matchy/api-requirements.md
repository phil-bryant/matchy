# Matchy API Requirements

## Scope

Applies to `matchy/api.py`.

R001  Statement: Expose an API health endpoint that reports service liveness.
Design: Register `GET /health` and return a JSON payload containing `status: ok`.
Tests:
- R001-T01: Create app and verify `/health` responds 200 with `status` set to `ok`.

R005  Statement: Convert missing-transaction service errors into HTTP 404 responses.
Design: Catch `ValueError` raised by match execution and translate it to `HTTPException` with status code 404. Request validation rejects empty transaction ids before service execution.
Tests:
- R005-T01: Stub service lookup failure and verify `/v1/matchy/runs` returns 404.
- R005-T02: Submit an empty transaction id and verify `/v1/matchy/runs` returns 422.

R010  Statement: Expose pending-transaction batch endpoint for driver-triggered runs.
Design: Register `POST /v1/matchy/runs/pending`, validate request fields, and delegate to service pending matcher.
Tests:
- R010-T01: Stub pending matcher and verify endpoint returns delegated rows with request values.

R015  Statement: Refresh the CLDR currencies cache during API startup.
Design: When `Settings.cldr_currencies_refresh_enabled` is true, `create_app()` constructs `CldrCurrenciesCache` and calls `refresh()` before returning the FastAPI app.
Tests:
- R015-T01: Enable the CLDR startup refresh flag, stub the cache object, create the app, and verify the cache refresh was called.

R045  Statement: Expose a human-confirm API endpoint with input validation and domain error mapping.
Design: Register `POST /v1/matchy/confirm`, validate `transaction_id`/`email_message_id` as non-empty ids, reject null bytes in `note`, and translate service `ValueError` to HTTP 404.
Tests:
- R045-T01: Stub service error and verify `/v1/matchy/confirm` returns 404.
- R045-T02: Stub service success and verify `/v1/matchy/confirm` delegates transaction, message id, and note.
- R045-T03: Submit a note containing a null byte and verify `/v1/matchy/confirm` returns 422.

R055  Statement: Protect mutating run/confirm endpoints with a shared Bearer token.
Design: Require `Authorization: Bearer <token>` for `POST /v1/matchy/runs`, `/v1/matchy/runs/pending`, and `/v1/matchy/confirm`, where `<token>` matches `MATCHY_API_AUTH_TOKEN`.
Tests:
- R055-T01: Call each mutating endpoint without an Authorization header and verify HTTP 401.
- R055-T02: Call a mutating endpoint with an invalid bearer token and verify HTTP 401.

R480  Statement: Emit startup timing logs only when explicit startup logging is enabled.
Design: `_startup_log` checks `MATCHY_STARTUP_LOG` and prints a single elapsed-phase line (including optional details)
only when the flag resolves to true.
Tests:
- R480-T01: Enable startup logging and verify `_startup_log` emits the requested phase/details payload.

R485  Statement: Lazily initialize MatchService and map initialization failures to HTTP 503.
Design: `_service` creates `MatchService` once per app instance and wraps constructor exceptions in `HTTPException`
503 with a stable "service unavailable" detail.
Tests:
- R485-T01: Force MatchService constructor failure and verify mutating endpoints return HTTP 503 with stable detail.

R490  Statement: Dispatch run requests through atomic batch matching when available.
Design: `run_matches` delegates to `match_transactions_atomic` when the service exposes it, falls back to per-id
`match_transaction` iteration otherwise, and maps `ValueError` failures to HTTP 404.
Tests:
- R490-T01: Provide a batch-capable service stub and verify the endpoint uses `match_transactions_atomic`.

R495  Statement: Delegate validated pending-run requests to MatchService batch matching.
Design: `run_pending_matches` forwards validated request values (`limit`, `lookback_days`, `trigger_source`,
`force_rematch`) directly to `MatchService.match_pending_transactions` and returns delegated rows.
Tests:
- R495-T01: Stub `match_pending_transactions` and verify forwarded request values are preserved in response payload.

R500  Statement: Delegate confirm requests and map domain misses to HTTP 404.
Design: `confirm_match` forwards validated `transaction_id`, `email_message_id`, and `note` to
`MatchService.confirm_match`, returning service payloads on success and converting service `ValueError` failures to 404.
Tests:
- R500-T01: Confirm endpoint delegates successful confirm requests and forwards all payload fields.
- R500-T02: Confirm endpoint maps service `ValueError` failures to HTTP 404.

## Changelog

- 2026-05-18: Added API requirements coverage for run and health paths.
- 2026-05-18: Added R010 pending-run endpoint requirements for external driver workflows.
- 2026-06-01: Added R015 startup refresh for the local CLDR currencies cache.
- 2026-06-03: Added run/confirm request validation and explicit confirm endpoint requirements.
- 2026-06-04: Added R055 Bearer-auth requirement for mutating API endpoints.
- 2026-06-06: Added R480-R500 startup/service-dispatch requirements and anchored tests for run/pending/confirm helper paths.
