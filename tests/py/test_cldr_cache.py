#R001: Python test lane coverage for local CLDR currencies cache population and freshness checks.
#R005: Python test lane coverage for tolerant CLDR cache refresh failures.

from __future__ import annotations

import requests

import matchy.cldr_cache as cldr_cache
from matchy.cldr_cache import CldrCurrenciesCache, CldrCurrencyMatcher


class StubSettings:
    def __init__(self, cache_path: str):
        self.cldr_currencies_cache_path = cache_path
        self.cldr_currencies_refresh_timeout_seconds = 2


class StubResponse:
    def __init__(self, payload, text: str = "", error: Exception | None = None):
        self._payload = payload
        self.text = text
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload


def test_cldr_cache_downloads_when_missing_or_version_changed(monkeypatch, tmp_path) -> None:
    #R001: Missing local cache downloads raw currencies.json and records the latest file commit sha.
    #R001-T01: Python test lane exists for initial cache download.
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        response = StubResponse([{"sha": "sha-1"}])
        if url == CldrCurrenciesCache.RAW_URL:
            response = StubResponse({}, '{"main":{"en":{"numbers":{"currencies":{"USD":{"displayName":"US Dollar"}}}}}}')
        return response

    monkeypatch.setattr(cldr_cache.requests, "get", fake_get)
    cache_path = tmp_path / "currencies.json"
    status = CldrCurrenciesCache(StubSettings(str(cache_path))).refresh()
    assert status["updated"] is True
    assert status["version"] == "sha-1"
    assert cache_path.read_text(encoding="utf-8").startswith('{"main"')
    assert cache_path.with_suffix(".json.sha").read_text(encoding="utf-8") == "sha-1\n"
    assert calls == [CldrCurrenciesCache.COMMITS_URL, CldrCurrenciesCache.RAW_URL]


def test_cldr_cache_skips_download_when_cached_version_is_current(monkeypatch, tmp_path) -> None:
    #R001: Matching cached sha skips the raw download while still checking the GitHub file history URL.
    #R001-T02: Python test lane exists for unchanged-version no-download behavior.
    cache_path = tmp_path / "currencies.json"
    cache_path.write_text('{"cached": true}', encoding="utf-8")
    cache_path.with_suffix(".json.sha").write_text("sha-1\n", encoding="utf-8")
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return StubResponse([{"sha": "sha-1"}])

    monkeypatch.setattr(cldr_cache.requests, "get", fake_get)
    status = CldrCurrenciesCache(StubSettings(str(cache_path))).refresh()
    assert status["updated"] is False
    assert cache_path.read_text(encoding="utf-8") == '{"cached": true}'
    assert calls == [CldrCurrenciesCache.COMMITS_URL]


def test_cldr_cache_keeps_existing_file_when_refresh_fails(monkeypatch, tmp_path) -> None:
    #R005: Network failures leave the existing cache content and version metadata untouched.
    #R005-T01: Python test lane exists for retaining stale cache after network failure.
    cache_path = tmp_path / "currencies.json"
    cache_path.write_text('{"cached": true}', encoding="utf-8")
    cache_path.with_suffix(".json.sha").write_text("sha-1\n", encoding="utf-8")

    def fake_get(url, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(cldr_cache.requests, "get", fake_get)
    status = CldrCurrenciesCache(StubSettings(str(cache_path))).refresh()
    assert status["updated"] is False
    assert status["version"] == "sha-1"
    assert cache_path.read_text(encoding="utf-8") == '{"cached": true}'


def test_cldr_cache_parses_currency_codes_and_symbols_from_cached_payload() -> None:
    #R010-T01: Cached CLDR payloads produce deduplicated currency codes and usable symbols.
    payload = {"main": {"en": {"numbers": {"currencies": {
        "USD": {"displayName": "US Dollar", "symbol": "$", "symbol-alt-narrow": "$"},
        "EUR": {"displayName": "Euro", "symbol": "€"},
        "XTS": {"displayName": "Testing Currency", "symbol": "¤"},
    }}}}}
    tokens = CldrCurrenciesCache.parse_currency_tokens(payload)
    assert "USD" in tokens
    assert "EUR" in tokens
    assert "$" in tokens
    assert "€" in tokens
    assert "¤" not in tokens


def test_cldr_currency_matcher_requires_standalone_codes_and_symbols() -> None:
    #R010-T02: Codes and symbols must not match as substrings inside larger alphanumeric tokens.
    matcher = CldrCurrencyMatcher(frozenset({"USD", "$", "€"}))
    assert matcher.contains_standalone_currency("USD 10.00")
    assert matcher.contains_standalone_currency("$10.00")
    assert matcher.contains_standalone_currency("total € 12")
    assert not matcher.contains_standalone_currency("xUSDx 10.00")
    assert not matcher.contains_standalone_currency("USDD 10.00")
    assert not matcher.contains_standalone_currency("receipt without money token")


def test_cldr_cache_returns_empty_tokens_when_cache_is_missing_or_malformed(tmp_path) -> None:
    #R010-T03: Missing or malformed local cache data leaves matching usable by producing an empty matcher.
    cache_path = tmp_path / "missing.json"
    assert CldrCurrenciesCache(StubSettings(str(cache_path))).currency_tokens() == frozenset()
    cache_path.write_text("{not-json", encoding="utf-8")
    assert CldrCurrenciesCache(StubSettings(str(cache_path))).currency_tokens() == frozenset()
