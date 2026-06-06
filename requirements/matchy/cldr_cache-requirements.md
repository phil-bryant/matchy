# Matchy CLDR Cache Requirements

## Scope

Applies to `matchy/cldr_cache.py`.

R560  Statement: Refresh local CLDR cache only when upstream file freshness changes.
Design: `refresh()` reads cached SHA metadata, fetches latest commit SHA for the CLDR currencies file, and downloads/writes raw JSON + SHA metadata only when SHA differs or cache file is missing.
Tests:
- R560-T01: Stub commits/raw URLs with no local cache and verify cache body and SHA metadata are written.
- R560-T02: Seed current cached SHA and verify refresh skips the raw download.

R565  Statement: Keep startup usable when CLDR refresh metadata reads or network calls fail.
Design: `refresh()` and `_read_text()` tolerate read/network/parse failures by logging warnings and returning status that preserves existing cache files/versions.
Tests:
- R565-T01: Seed cache files, force refresh network failure, and verify cached body/version remain unchanged.

R570  Statement: Parse CLDR payloads into normalized currency code/symbol token sets.
Design: `parse_currency_tokens()` extracts codes and symbol variants from `main.en.numbers.currencies`, normalizes case/whitespace, and drops placeholder symbols via `_clean_symbol`/`_is_placeholder_symbol`.
Tests:
- R570-T01: Parse sample CLDR payload and verify normalized code/symbol tokens are deduplicated while placeholders are excluded.

R575  Statement: Match currency codes/symbols only as standalone tokens.
Design: `CldrCurrencyMatcher` boundary checks reject alphanumeric substring matches for both 3-letter codes and symbol tokens while still matching real standalone occurrences.
Tests:
- R575-T01: Verify matcher accepts standalone code/symbol occurrences and rejects embedded substring forms.

R580  Statement: Expose resilient currency token/matcher loading from local cache files.
Design: `currency_tokens()` and `currency_matcher()` parse cached CLDR data and return empty token sets when cache files are missing or malformed so downstream matching remains operational.
Tests:
- R580-T01: Verify missing or malformed cache files return empty token sets instead of raising.

## Changelog

- 2026-06-01: Added CLDR currencies cache freshness and failure-tolerance requirements.
- 2026-06-01: Added cached CLDR currency-token parsing and standalone matching requirements.
- 2026-06-06: Rebased CLDR cache traceability onto shard-1 ID band R560-R580 with anchored tests.
