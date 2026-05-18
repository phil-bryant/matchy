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

## Changelog

- 2026-05-18: Added API requirements coverage for run and health paths.
