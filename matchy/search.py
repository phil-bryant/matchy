from __future__ import annotations

from datetime import timedelta
import logging
import re
from time import monotonic

import requests

from .models import EmailCandidate
from .runtime_profile import _runtime_profile_log

LOGGER = logging.getLogger(__name__)


class SearchMixin:
    #R005: Build deterministic scoped search terms from merchant + transaction text. Capped at two
    #R005: terms because each emitted query is a slow full-mailbox scan; the two most distinctive
    #R005: merchant tokens (counterparty first, then description) carry almost all of the signal.
    _MAX_SEARCH_TERMS = 2

    #R040: Execute the scoped retrieval fallback chain (terms+date → terms-only → broad-term → empty)
    #R040: without yet creating a match_run row. Query-tier requests intentionally use scoped
    #R040: Mailcart syntax (`subject:`/`body:` plus optional `from:`/`to:` date bounds) and union
    #R040: results across terms to improve recall while preserving deterministic ordering.
    def _search_candidates(self, txn, transaction_id: str) -> list[EmailCandidate]:
        if self._mailcart_in_cooldown(transaction_id=transaction_id):
            return []
        terms = self._extract_search_terms(txn.description, txn.counterparty_name)
        #R040: Each mailcart search is a ~15-20s full-mailbox Graph scan, and the driver already runs
        #R040: several transactions in parallel, so we must keep per-transaction load to ~one scan.
        #R040: Issue queries one at a time and stop at the first that returns anything (early-stop):
        #R040: body matching leads because the merchant name reliably appears in receipt/confirmation
        #R040: bodies, so the most distinctive term's body query usually catches the right email on the
        #R040: first request. Subject, a window-free retry, and the historical recency fallback only run
        #R040: when earlier queries come back empty. We deliberately do NOT fan out concurrently —
        #R040: parallel scans saturate the single mailcart instance and push every request past its
        #R040: timeout.
        query_plan = (
            self._build_scoped_queries(terms, txn.date, fields=("body",), include_date_window=True)
            + self._build_scoped_queries(terms, txn.date, fields=("subject",), include_date_window=True)
            + self._build_scoped_queries(terms, txn.date, fields=("body",), include_date_window=False)
            + [""]
        )
        for query in query_plan:
            rows = self._search_mailcart(query=query, transaction_id=transaction_id, limit=75)
            candidates = self._dedupe_candidates(rows, limit=75)
            if candidates:
                return candidates
            if self._mailcart_in_cooldown(transaction_id=transaction_id):
                return []
        return []

    #R040: De-duplicate a single search result by message_id while preserving order and dropping rows
    #R040: without an id, capped at `limit`.
    @staticmethod
    def _dedupe_candidates(rows: list[EmailCandidate], limit: int) -> list[EmailCandidate]:
        deduped: dict[str, EmailCandidate] = {}
        for candidate in rows:
            message_id = str(candidate.message_id)
            if not message_id or message_id in deduped:
                continue
            deduped[message_id] = candidate
            if len(deduped) >= limit:
                break
        return list(deduped.values())

    #R040: A slow search (Timeout) means Mailcart is up but busy, not down: skip just that query and
    #R040: let the caller fall through to the next tier / the recency fallback. Only connection-level
    #R040: failures and 5xx responses arm the shared cooldown. Client errors (4xx) are real bugs and
    #R040: propagate so they are not silently masked.
    def _search_mailcart(self, query: str, transaction_id: str, limit: int) -> list[EmailCandidate]:
        try:
            return self._mailcart_client.search_candidates(query=query, limit=limit)
        except requests.exceptions.Timeout as exc:
            LOGGER.warning("mailcart search timed out query=%r transaction_id=%s error=%s", query, transaction_id, exc)
            return []
        except Exception as exc:
            LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", query, transaction_id, exc)
            if self._is_transient_mailcart_error(exc):
                self._mark_mailcart_temporarily_unavailable(transaction_id=transaction_id)
                return []
            raise

    #R800: Skip Mailcart search work while a transient-failure cooldown window remains active.
    def _mailcart_in_cooldown(self, transaction_id: str) -> bool:
        now = monotonic()
        unavailable_until = float(getattr(self, "_mailcart_unavailable_until_monotonic", 0.0) or 0.0)
        if now < unavailable_until:
            remaining_seconds = unavailable_until - now
            _runtime_profile_log(
                "mailcart-search-skipped-cooldown",
                f"transaction_id={transaction_id} remaining_seconds={remaining_seconds:0.1f}",
            )
            return True
        return False

    #R801: Classify connection and HTTP 5xx request failures as transient Mailcart errors eligible for cooldown.
    def _is_transient_mailcart_error(self, exc: Exception) -> bool:
        if isinstance(exc, requests.exceptions.ConnectionError):
            return True
        if isinstance(exc, requests.exceptions.HTTPError):
            response = getattr(exc, "response", None)
            status_code = int(getattr(response, "status_code", 0) or 0)
            return status_code >= 500
        if isinstance(exc, requests.exceptions.RequestException):
            response = getattr(exc, "response", None)
            status_code = int(getattr(response, "status_code", 0) or 0)
            return status_code >= 500
        return False

    #R802: Start a monotonic cooldown window after transient Mailcart failures so subsequent searches back off briefly.
    def _mark_mailcart_temporarily_unavailable(self, transaction_id: str) -> None:
        cooldown_seconds = int(getattr(self, "_mailcart_failure_cooldown_seconds", 15) or 15)
        if cooldown_seconds > 0:
            next_available = monotonic() + cooldown_seconds
            self._mailcart_unavailable_until_monotonic = next_available
            _runtime_profile_log(
                "mailcart-search-cooldown-started",
                f"transaction_id={transaction_id} cooldown_seconds={cooldown_seconds}",
            )

    #R803: Derive deterministic search terms from counterparty/description text by filtering short, numeric, and duplicate tokens.
    def _extract_search_terms(self, description: str, counterparty_name: str) -> list[str]:
        ordered_tokens: list[str] = []
        seen: set[str] = set()
        sources = [counterparty_name or "", description or ""]
        for source in sources:
            normalized = re.sub(r"[^a-z0-9\s]", " ", source.lower())
            for token in normalized.split():
                if len(token) < 4:
                    continue
                if token.isdigit():
                    continue
                if re.search(r"[a-z]", token) is None:
                    continue
                if token in seen:
                    continue
                seen.add(token)
                ordered_tokens.append(token)
                if len(ordered_tokens) >= self._MAX_SEARCH_TERMS:
                    return ordered_tokens
        return ordered_tokens

    #R804: Build scoped Mailcart queries for each term/field combination, optionally appending the transaction date window suffix.
    def _build_scoped_queries(
        self,
        terms: list[str],
        txn_date,
        fields: tuple[str, ...] = ("body",),
        include_date_window: bool = True,
    ) -> list[str]:
        if not terms:
            return []
        date_window = self._date_window_suffix(txn_date) if include_date_window else ""
        scoped_queries: list[str] = []
        for term in terms:
            for field in fields:
                scoped_queries.append(f"{field}:{term}{date_window}")
        return scoped_queries

    #R805: Emit an inclusive from/to date window suffix around the transaction date using configured search window days.
    def _date_window_suffix(self, txn_date) -> str:
        window_days = int(getattr(self._settings, "mailcart_search_date_window_days", 45) or 45)
        if window_days <= 0:
            return ""
        from_date = (txn_date - timedelta(days=window_days)).date().isoformat()
        to_date = (txn_date + timedelta(days=window_days)).date().isoformat()
        return f" from:{from_date} to:{to_date}"
