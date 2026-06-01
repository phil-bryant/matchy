---
name: CLDR currency filter
overview: Parse cached CLDR currencies into matchable currency tokens and use them to drop email candidates that do not contain a standalone valid currency code or symbol before scoring/AI selection.
todos:
  - id: parse-cldr-currency-tokens
    content: Add CLDR cache parser and standalone token matcher in cldr_cache.py
    status: completed
  - id: filter-service-candidates
    content: Filter enriched service candidates before ranking and AI selection
    status: completed
  - id: update-requirements
    content: Document the new parser and candidate-filtering behavior
    status: completed
  - id: add-tests
    content: Add parser, standalone matching, and service filtering tests
    status: completed
  - id: verify-tests
    content: Run targeted and broader pytest checks
    status: completed
isProject: false
---

# CLDR Currency Filter

Implement this as a narrow extension of the existing CLDR cache and service pipeline.

- Add parsing helpers to [`matchy/cldr_cache.py`](matchy/cldr_cache.py):
  - Load the cached CLDR JSON from `Settings.cldr_currencies_cache_path`.
  - Extract ISO currency codes from the `currencies` keys and symbols from each currency entry, including `symbol`, `symbol-alt-narrow`, and similar `symbol-alt-*` fields.
  - Ignore empty/placeholder symbols and deduplicate tokens into an immutable set.
  - Add a matcher that checks candidate subject/preview/body text for standalone tokens: alphabetic codes like `USD` must be bounded by non-alphanumeric characters; symbols like `$`/`€` must not be embedded in alphanumeric text.
  - If the cache is missing or malformed, return an empty token set and let matching continue unfiltered, matching the cache’s existing tolerant offline behavior.

- Wire the filter into [`matchy/service.py`](matchy/service.py):
  - Construct/load the parsed CLDR matcher once in `MatchService.__init__`.
  - Keep `_search_candidates()` as-is so Mailcart recall and early-stop behavior stay unchanged.
  - After `_enrich_candidate_bodies()` and before `rank_candidates(...)`, filter candidates by `subject + preview + body_text` containing a standalone valid CLDR currency code or symbol.
  - The current transaction model has no currency field, so this will require any valid CLDR currency token rather than a transaction-specific currency.

- Update requirements docs:
  - Extend [`requirements/matchy/cldr_cache-requirements.md`](requirements/matchy/cldr_cache-requirements.md) with parser/token extraction and standalone matching requirements.
  - Extend [`requirements/matchy/api-requirements.md`](requirements/matchy/api-requirements.md) or add a service requirements entry if one already exists for the candidate filtering behavior.

- Add focused tests:
  - In [`tests/py/test_cldr_cache.py`](tests/py/test_cldr_cache.py), verify CLDR codes/symbols are parsed from a sample payload, duplicates/placeholders are ignored, and standalone matching rejects substrings like `USDD` or `xUSDx` while accepting `USD 10.00`, `$10.00`, and `total € 12`.
  - In [`tests/py/test_service.py`](tests/py/test_service.py), verify the full pipeline filters enriched candidates before ranking/AI: a candidate with `body_text="total $35.99"` remains and one with no currency token is excluded.
  - Add a missing-cache/malformed-cache test showing the service continues unfiltered instead of failing.

- Verification:
  - Run the targeted Python tests first: `python -m pytest tests/py/test_cldr_cache.py tests/py/test_service.py`.
  - If those pass, run the broader Python lane if practical: `python -m pytest tests/py`.