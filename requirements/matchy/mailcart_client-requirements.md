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

R045  Statement: Resolve the Mailcart CA bundle explicitly instead of relying on REQUESTS_CA_BUNDLE.
Design: Determine CA bundle precedence (MATCHY_MAILCART_CA_BUNDLE override, REQUESTS_CA_BUNDLE/SSL_CERT_FILE, local mkcert root, then certifi default) and configure `requests` to use it so mkcert-signed localhost certificates are accepted. If an explicit bundle env var is set but points to a missing path, fail fast with a configuration error.
Tests:
- R045-T01: Verify CA bundle selection order and that an explicit override takes precedence.
- R045-T02: Construct `MailcartClient` with a missing explicit `MATCHY_MAILCART_CA_BUNDLE` path and verify initialization fails fast with a configuration error.

R050  Statement: Validate Mailcart transport configuration before processing work.
Design: `MailcartClient` exposes a startup preflight health probe (`GET /health`) using the same configured base URL and TLS verify bundle as search/move calls. `MatchService` runs this one-shot probe when initialized (configurable via `MATCHY_MAILCART_STARTUP_HEALTHCHECK`) so worker-triggered runs fail fast with actionable transport diagnostics instead of retry-loop noise.
Tests:
- R050-T01: Enable startup preflight and verify `MatchService` invokes `MailcartClient.startup_preflight_healthcheck()` exactly once during initialization.
- R050-T02: Verify startup preflight hits `/health` and forwards the resolved TLS verify bundle + configured timeout.
- R050-T03: Simulate startup preflight transport failure and verify the surfaced error includes base URL and verify context.

## Changelog

- 2026-05-18: Added Mailcart client requirements and numbered tests.
- 2026-05-19: Added R010 single-message fetch so matchy can enrich candidates with full body before scoring.
- 2026-05-28: Added R015 strict HTTPS-only Mailcart base URL enforcement with fail-fast validation.
- 2026-05-29: Added R045 explicit CA bundle resolution for mkcert localhost certificates.
- 2026-06-03: Updated R045 with fail-fast missing-bundle handling and added R050 startup transport preflight requirements.
