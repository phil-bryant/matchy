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

R010  Statement: Fetch a single Mailcart message envelope so callers can enrich search candidates with the full body.
Design: `get_message(message_id)` issues `GET /v1/messages/{id}` against Mailcart with the optional bearer header, returns the raw payload dict (containing at minimum `subject`, `sender`, `preview`, `html_body`, `text_body`, `body_text`), and returns an empty dict for 404 responses so a per-id miss does not abort enrichment of the whole candidate list. Empty `message_id` short-circuits to an empty dict without issuing an HTTP request.
Tests:
- R010-T01: Stub `requests.get` to return a payload with body fields and verify the dict is returned verbatim; verify an empty `message_id` returns `{}` without a request.
- R010-T02: Stub `requests.get` to return a 404 and verify `get_message` returns an empty dict (no exception).

R015  Statement: Reject non-HTTPS Mailcart base URLs.
Design: `MailcartClient` validates `MAILCART_SERVICE_BASE_URL` at initialization and raises a runtime error unless the configured base URL starts with `https://`. The client must never auto-upgrade or fallback from `http` to `https`.
Tests:
- R015-T01: Construct `MailcartClient` with an `http://` base URL and verify initialization raises a runtime error that states HTTPS is required.

## Changelog

- 2026-05-18: Added Mailcart client requirements and numbered tests.
- 2026-05-19: Added R010 single-message fetch so matchy can enrich candidates with full body before scoring.
- 2026-05-28: Added R015 strict HTTPS-only Mailcart base URL enforcement with fail-fast validation.
