# Matchy API Requirements

## Scope

Applies to `matchy/api.py`.

R001  Statement: Expose an API health endpoint that reports service liveness.
Design: Register `GET /health` and return a JSON payload containing `status: ok`.
Tests:
- R001-T01: Create app and verify `/health` responds 200 with `status` set to `ok`.

R005  Statement: Convert missing-transaction service errors into HTTP 404 responses.
Design: Catch `ValueError` raised by match execution and translate it to `HTTPException` with status code 404.
Tests:
- R005-T01: Stub service lookup failure and verify `/v1/matchy/runs` returns 404.

R010  Statement: Expose pending-transaction batch endpoint for driver-triggered runs.
Design: Register `POST /v1/matchy/runs/pending`, validate request fields, and delegate to service pending matcher.
Tests:
- R010-T01: Stub pending matcher and verify endpoint returns delegated rows with request values.

## Changelog

- 2026-05-18: Added API requirements coverage for run and health paths.
- 2026-05-18: Added R010 pending-run endpoint requirements for external driver workflows.
