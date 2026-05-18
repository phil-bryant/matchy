# Matchy Mailcart Client Requirements

## Scope

Applies to `matchy/mailcart_client.py`.

R001  Statement: Attach bearer authorization only when token configuration is present.
Design: Build request headers with JSON content type and optional `Authorization: Bearer ...` when token is non-empty.
Tests:
- R001-T01: Construct client with and without token and verify header inclusion behavior.

R005  Statement: Convert search responses into valid email candidates.
Design: Parse message rows into `EmailCandidate` values and filter out entries with empty `message_id`.
Tests:
- R005-T01: Stub search response with one empty message_id and verify only valid candidate remains.

## Changelog

- 2026-05-18: Added Mailcart client requirements and numbered tests.
