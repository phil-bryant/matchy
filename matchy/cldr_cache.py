from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path

import requests

from .settings import Settings

LOGGER = logging.getLogger(__name__)
_PLACEHOLDER_SYMBOLS = frozenset({"¤"})


class CldrCurrencyMatcher:
    def __init__(self, tokens: frozenset[str]):
        clean_tokens = frozenset(token.strip() for token in tokens if token.strip())
        self.tokens = clean_tokens
        self._codes = tuple(sorted(token.upper() for token in clean_tokens if token.isalpha() and len(token) == 3))
        symbols = (token for token in clean_tokens if not (token.isalpha() and len(token) == 3))
        self._symbols = tuple(sorted(symbols, key=len, reverse=True))

    #R010: Match only standalone currency codes/symbols so substrings like xUSDx do not scope candidates.
    def contains_standalone_currency(self, text: str) -> bool:
        value = text or ""
        matched = False
        index = 0
        while not matched and index < len(self._codes):
            pattern = r"(?<![A-Za-z0-9])" + re.escape(self._codes[index]) + r"(?![A-Za-z0-9])"
            matched = re.search(pattern, value, re.IGNORECASE) is not None
            index += 1
        index = 0
        while not matched and index < len(self._symbols):
            matched = self._symbol_occurs_standalone(self._symbols[index], value)
            index += 1
        return matched

    @staticmethod
    def _symbol_occurs_standalone(symbol: str, text: str) -> bool:
        found = False
        start = 0
        while not found and start >= 0:
            position = text.find(symbol, start)
            if position >= 0:
                found = CldrCurrencyMatcher._symbol_at_position_is_standalone(symbol, text, position)
                start = position + 1
            if position < 0:
                start = -1
        return found

    @staticmethod
    def _symbol_at_position_is_standalone(symbol: str, text: str, position: int) -> bool:
        left = text[position - 1] if position > 0 else ""
        right_index = position + len(symbol)
        right = text[right_index] if right_index < len(text) else ""
        left_ok = not left.isalnum() if symbol.isalnum() else not left.isalpha()
        right_ok = not right.isalnum() if symbol.isalnum() else not right.isalpha()
        return left_ok and right_ok


class CldrCurrenciesCache:
    RAW_URL = (
        "https://raw.githubusercontent.com/unicode-org/cldr-json/main/"
        "cldr-json/cldr-numbers-full/main/en/currencies.json"
    )
    COMMITS_URL = (
        "https://api.github.com/repos/unicode-org/cldr-json/commits"
        "?sha=main&path=cldr-json/cldr-numbers-full/main/en/currencies.json&per_page=1"
    )

    def __init__(self, settings: Settings):
        self._cache_path = Path(settings.cldr_currencies_cache_path).expanduser()
        self._version_path = self._cache_path.with_suffix(self._cache_path.suffix + ".sha")
        self._timeout_seconds = int(settings.cldr_currencies_refresh_timeout_seconds or 5)

    #R001: Cache the CLDR en/currencies.json file locally and refresh only when GitHub reports a new file commit.
    #R005: Treat refresh failures as startup warnings so an existing cache can keep the app usable offline.
    def refresh(self) -> dict[str, object]:
        cached_version = self._read_text(self._version_path)
        status: dict[str, object] = {"cache_path": str(self._cache_path), "version": cached_version, "updated": False}
        try:
            latest_version = self._latest_version()
            needs_download = latest_version != cached_version or not self._cache_path.exists()
            if needs_download:
                self._write_cache(self._download_body(), latest_version)
            status = {"cache_path": str(self._cache_path), "version": latest_version, "updated": needs_download}
        except (OSError, ValueError, requests.RequestException) as exc:
            LOGGER.warning("cldr currencies cache refresh skipped path=%s error=%s", self._cache_path, exc)
        return status

    #R010: Parse cached CLDR currency codes and symbols for standalone candidate text matching.
    def currency_matcher(self) -> CldrCurrencyMatcher:
        return CldrCurrencyMatcher(self.currency_tokens())

    def currency_tokens(self) -> frozenset[str]:
        tokens: frozenset[str] = frozenset()
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            tokens = self.parse_currency_tokens(payload)
        except (OSError, TypeError, ValueError) as exc:
            LOGGER.warning("cldr currencies cache parse skipped path=%s error=%s", self._cache_path, exc)
        return tokens

    @staticmethod
    def parse_currency_tokens(payload: dict) -> frozenset[str]:
        tokens: set[str] = set()
        currencies = CldrCurrenciesCache._currencies_section(payload)
        for code, entry in currencies.items():
            clean_code = str(code or "").strip().upper()
            if clean_code:
                tokens.add(clean_code)
            if isinstance(entry, dict):
                for key, raw_value in entry.items():
                    if key == "symbol" or key.startswith("symbol-alt-"):
                        symbol = CldrCurrenciesCache._clean_symbol(raw_value)
                        if symbol:
                            tokens.add(symbol)
        return frozenset(tokens)

    @staticmethod
    def _currencies_section(payload: dict) -> dict:
        section = {}
        if isinstance(payload, dict):
            main = payload.get("main", {})
            en = main.get("en", {}) if isinstance(main, dict) else {}
            numbers = en.get("numbers", {}) if isinstance(en, dict) else {}
            currencies = numbers.get("currencies", {}) if isinstance(numbers, dict) else {}
            if isinstance(currencies, dict):
                section = currencies
        return section

    @staticmethod
    def _clean_symbol(value) -> str:
        symbol = str(value or "").strip()
        if CldrCurrenciesCache._is_placeholder_symbol(symbol):
            symbol = ""
        return symbol

    @staticmethod
    def _is_placeholder_symbol(symbol: str) -> bool:
        placeholder = (not symbol) or symbol in _PLACEHOLDER_SYMBOLS or symbol.startswith("↑")
        if len(symbol) == 1 and not placeholder:
            placeholder = unicodedata.category(symbol) != "Sc" and not symbol.isalnum()
        return placeholder

    def _latest_version(self) -> str:
        response = requests.get(
            self.COMMITS_URL,
            headers={"Accept": "application/vnd.github+json"},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        version = ""
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            version = str(payload[0].get("sha") or "")
        if not version:
            raise ValueError("GitHub commits API did not return a file commit sha")
        return version

    def _download_body(self) -> str:
        response = requests.get(self.RAW_URL, timeout=self._timeout_seconds)
        response.raise_for_status()
        body = response.text
        json.loads(body)
        return body

    def _write_cache(self, body: str, version: str) -> None:
        self._ensure_cache_dir()
        self._write_file(self._cache_path, body)
        self._write_file(self._version_path, version + "\n")

    def _ensure_cache_dir(self) -> None:
        missing_dirs: list[Path] = []
        current = self._cache_path.parent
        while not current.exists():
            missing_dirs.append(current)
            current = current.parent
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        for path in missing_dirs:
            os.chmod(path, 0o770)  # nosec B103 # nosemgrep

    @staticmethod
    def _write_file(path: Path, content: str) -> None:
        temp_path = path.with_name("." + path.name + ".tmp")
        temp_path.write_text(content, encoding="utf-8")
        os.chmod(temp_path, 0o660)  # nosec B103 # nosemgrep
        temp_path.replace(path)
        os.chmod(path, 0o660)  # nosec B103 # nosemgrep

    @staticmethod
    def _read_text(path: Path) -> str:
        value = ""
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
        return value
