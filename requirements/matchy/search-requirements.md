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

## Changelog

- 2026-06-05: Extracted R005 (search-term/query construction) and R040 (scoped retrieval tiering with early-stop, de-dup, and Mailcart cooldown) from `service.py` into `search.py`/`SearchMixin`.
