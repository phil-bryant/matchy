# Matchy CLDR Cache Requirements

## Scope

Applies to `matchy/cldr_cache.py`.

R001  Statement: Cache the CLDR English currencies JSON file locally and refresh by GitHub file freshness.
Design: `CldrCurrenciesCache.refresh()` checks GitHub's commits API for the newest commit touching `cldr-json/cldr-numbers-full/main/en/currencies.json`, compares that SHA with local metadata, and downloads the raw JSON file only when the SHA differs or the cache file is missing.
Tests:
- R001-T01: Stub the GitHub commits and raw URLs, run refresh with no local cache, and verify the JSON file and SHA metadata are written.
- R001-T02: Stub the commits URL with the cached SHA, run refresh, and verify the raw URL is not fetched.

R005  Statement: Preserve startup usability when CLDR refresh fails.
Design: Refresh catches filesystem, invalid-payload, and `requests` failures, logs a warning, and leaves any existing cache content and metadata untouched.
Tests:
- R005-T01: Seed a local cache, make the freshness check raise a `requests` error, and verify cached content and SHA metadata remain unchanged.

R010  Statement: Parse cached CLDR currencies into standalone-matchable tokens.
Design: `CldrCurrenciesCache.currency_tokens()` reads the cached CLDR `main.en.numbers.currencies`
payload, extracts currency codes plus `symbol` and `symbol-alt-*` values, drops empty/placeholder
symbols, and exposes a `CldrCurrencyMatcher` that matches only standalone codes/symbols in candidate
text. Missing or malformed cache files produce an empty token set so matching remains usable offline.
Tests:
- R010-T01: Parse sample CLDR payload and verify codes/symbols dedupe while placeholders are ignored.
- R010-T02: Verify standalone matching accepts currency tokens and rejects substring forms.
- R010-T03: Verify a missing or malformed cache returns an empty token set instead of raising.

## Changelog

- 2026-06-01: Added CLDR currencies cache freshness and failure-tolerance requirements.
- 2026-06-01: Added cached CLDR currency-token parsing and standalone matching requirements.
