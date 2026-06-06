# Matchy Search Requirements

## Scope

Applies to `matchy/search.py`. Provides `SearchMixin`, the scoped Mailcart retrieval concern extracted
from the service orchestration module: deterministic search-term/query construction and the tiered
retrieval fallback chain with Mailcart cooldown handling. Mixed into `MatchService` so the public
`match_transaction` contract is unchanged.

R005  Statement: Build deterministic normalized search queries from transaction text.
Design: Normalize description/counterparty text to lowercase alphanumeric tokens, drop short/numeric tokens, and select deterministic token subsets (capped at two terms). `_build_scoped_queries`/`_date_window_suffix` emit `subject:`/`body:` scoped Mailcart syntax with optional `from:`/`to:` date bounds.
Tests:
- R005-T01: Call `_extract_search_terms`/`_build_scoped_queries` with noisy text and verify normalized deterministic scoped outputs.

R040  Statement: Execute the scoped retrieval fallback chain (terms+date -> terms-only -> broad-term -> empty) without yet creating a match_run row.
Design: `_search_candidates` intentionally uses scoped Mailcart syntax and unions results across terms to improve recall while preserving deterministic ordering. Each mailcart search is a ~15-20s full-mailbox Graph scan; the driver already runs several transactions in parallel, so per-transaction load must be kept to ~one scan. Queries are issued one at a time and stop at the first that returns anything (early-stop); body matching leads because the merchant name reliably appears in receipt/confirmation bodies. Subject, a window-free retry, and the recency fallback only run when earlier queries come back empty. Results are de-duplicated by message_id while preserving order. Transient connection/5xx failures arm a shared cooldown via `_mark_mailcart_temporarily_unavailable`; timeouts and 4xx are not treated as outages.
Tests:
- R040-T01: Verify early-stop behavior returns on first successful tier and subsequent tiers are not invoked.
- R040-T02: Verify result de-duplication preserves deterministic order.

R800  Statement: Honor transient Mailcart cooldown windows before issuing search requests.
Design: `_mailcart_in_cooldown` compares current monotonic time against `_mailcart_unavailable_until_monotonic`,
logging remaining cooldown when active and returning true until the window expires.
Tests:
- R800-T01: Verify cooldown checks return true before expiry and false after expiry.

R801  Statement: Classify transient Mailcart failures for cooldown handling.
Design: `_is_transient_mailcart_error` returns true for connection errors and request/http exceptions with 5xx status,
and false for non-5xx or unrelated exceptions.
Tests:
- R801-T01: Verify transient classifier behavior across connection, 5xx, 4xx, and unrelated exceptions.

R802  Statement: Start cooldown windows after transient Mailcart failures.
Design: `_mark_mailcart_temporarily_unavailable` sets `_mailcart_unavailable_until_monotonic` to now plus configured
cooldown seconds (when positive) and emits runtime-profile diagnostics.
Tests:
- R802-T01: Verify cooldown marker stores the expected unavailable-until timestamp from configured cooldown seconds.

R803  Statement: Extract deterministic high-signal Mailcart search terms from transaction text.
Design: `_extract_search_terms` normalizes counterparty+description text, drops short/numeric/non-alpha tokens,
deduplicates terms, and preserves first-seen order up to `_MAX_SEARCH_TERMS`.
Tests:
- R803-T01: Verify extracted search terms preserve deterministic normalized ordering from transaction text.

R804  Statement: Compose scoped Mailcart query strings from terms and fields.
Design: `_build_scoped_queries` emits one query per `(term, field)` pair and appends the date-window suffix when enabled.
Tests:
- R804-T01: Verify scoped query builder emits deterministic field+term combinations with optional date windows.

R805  Statement: Build inclusive search date-window suffixes around transaction timestamps.
Design: `_date_window_suffix` uses configurable `mailcart_search_date_window_days` to emit `from:` and `to:` date bounds,
returning empty suffix when configured window is non-positive.
Tests:
- R805-T01: Verify date-window suffix uses expected inclusive bounds for configured transaction dates.

## Changelog

- 2026-06-05: Extracted R005 (search-term/query construction) and R040 (scoped retrieval tiering with early-stop, de-dup, and Mailcart cooldown) from `service.py` into `search.py`/`SearchMixin`.
- 2026-06-06: Added R800-R805 helper requirements for cooldown classification, search-term extraction, and scoped query/date-window builders.
