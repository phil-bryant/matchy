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

## Changelog

- 2026-05-18: Added API requirements coverage for run and health paths.
- 2026-05-18: Added R010 pending-run endpoint requirements for external driver workflows.
- 2026-06-01: Added R015 startup refresh for the local CLDR currencies cache.
- 2026-06-03: Added run/confirm request validation and explicit confirm endpoint requirements.
