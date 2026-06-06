from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, as_completed
import logging

from .models import EmailCandidate

LOGGER = logging.getLogger(__name__)


class EnrichmentMixin:
    #R015: Replace each candidate's body_text with the full email body fetched from Mailcart so that
    #R015: amount/keyword/compact-merchant hints can score against the real message body. Returns the
    #R015: original candidates unchanged when the feature flag is off or when the client is missing
    #R015: get_message (older Mailcart deployments). Per-candidate failures fall through to the
    #R015: original candidate so a flaky message id does not poison the whole run.
    def _enrich_candidate_bodies(self, candidates: list[EmailCandidate], transaction_id: str) -> list[EmailCandidate]:
        result = candidates
        config = self._body_enrichment_config(candidates)
        if config is not None:
            get_message, enrich_count, timeout_seconds, max_workers, per_message_timeout = config
            message_ids = self._unique_message_ids(candidates, enrich_count)
            payload_by_id = self._fetch_message_payloads(
                get_message, message_ids, transaction_id, max_workers, timeout_seconds, per_message_timeout,
            )
            result = self._apply_body_enrichment(candidates, enrich_count, payload_by_id)
        return result

    def _body_enrichment_config(self, candidates: list[EmailCandidate]):
        config = None
        enabled = bool(getattr(self._settings, "mailcart_body_enrichment_enabled", False))
        get_message = getattr(self._mailcart_client, "get_message", None)
        if candidates and enabled and callable(get_message):
            limit = int(getattr(self._settings, "mailcart_body_enrichment_limit", 75) or 75)
            timeout_seconds = max(1, int(getattr(self._settings, "mailcart_body_enrichment_timeout_seconds", 25) or 25))
            max_workers = max(1, int(getattr(self._settings, "mailcart_body_enrichment_max_workers", 8) or 8))
            per_message_timeout = max(1, int(getattr(self._settings, "mailcart_get_message_timeout_seconds", 6) or 6))
            enrich_count = min(len(candidates), limit)
            if enrich_count >= 1:
                config = (get_message, enrich_count, timeout_seconds, max_workers, per_message_timeout)
        return config

    def _unique_message_ids(self, candidates: list[EmailCandidate], enrich_count: int) -> list[str]:
        message_ids: list[str] = []
        for index in range(enrich_count):
            message_id = str(candidates[index].message_id)
            if message_id not in message_ids:
                message_ids.append(message_id)
        return message_ids

    def _fetch_message_payloads(self, get_message, message_ids, transaction_id,
                                max_workers, timeout_seconds, per_message_timeout) -> dict[str, dict]:
        payload_by_id: dict[str, dict] = {}
        future_to_message_id: dict[Future, str] = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, len(message_ids))) as executor:
            for message_id in message_ids:
                future_to_message_id[executor.submit(get_message, message_id, per_message_timeout)] = message_id
            try:
                for future in as_completed(future_to_message_id, timeout=timeout_seconds):
                    message_id = future_to_message_id[future]
                    try:
                        payload_by_id[message_id] = future.result() or {}
                    except Exception as exc:
                        LOGGER.warning(
                            "mailcart get_message failed message_id=%s transaction_id=%s error=%s",
                            message_id, transaction_id, exc,
                        )
            except TimeoutError:
                unresolved_count = len([future for future in future_to_message_id if not future.done()])
                LOGGER.warning(
                    "mailcart body enrichment timed out transaction_id=%s unresolved_candidates=%s timeout_seconds=%s",
                    transaction_id, unresolved_count, timeout_seconds,
                )
        return payload_by_id

    def _enrichment_body_text(self, payload) -> str:
        body_text = ""
        if payload:
            body_text = (
                str(payload.get("text_body") or "").strip()
                or str(payload.get("html_body") or "").strip()
                or str(payload.get("body_text") or "").strip()
            )
        return body_text

    def _apply_body_enrichment(self, candidates, enrich_count, payload_by_id) -> list[EmailCandidate]:
        enriched: list[EmailCandidate] = []
        for index in range(enrich_count):
            candidate = candidates[index]
            payload = payload_by_id.get(str(candidate.message_id))
            body_text = self._enrichment_body_text(payload)
            if body_text:
                enriched.append(EmailCandidate(
                    message_id=candidate.message_id,
                    subject=candidate.subject or str(payload.get("subject") or ""),
                    preview=candidate.preview or str(payload.get("preview") or ""),
                    received_at=candidate.received_at,
                    sender=candidate.sender or str(payload.get("sender") or ""),
                    body_text=body_text,
                ))
            else:
                enriched.append(candidate)
        if len(candidates) > enrich_count:
            enriched.extend(candidates[enrich_count:])
        return enriched

    #R050: Scope matchable candidates to messages containing a standalone CLDR currency code or symbol.
    def _filter_currency_candidates(self, candidates: list[EmailCandidate]) -> list[EmailCandidate]:
        filtered = candidates
        matcher = getattr(self, "_cldr_currency_matcher", None)
        if candidates and matcher is not None and getattr(matcher, "tokens", frozenset()):
            filtered = []
            for candidate in candidates:
                text_blob = f"{candidate.subject} {candidate.preview} {candidate.body_text}"
                if matcher.contains_standalone_currency(text_blob):
                    filtered.append(candidate)
        return filtered
