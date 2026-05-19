from __future__ import annotations

from datetime import datetime, timezone

import requests

from .models import EmailCandidate
from .settings import Settings


class MailcartClient:
    def __init__(self, settings: Settings):
        self._base = settings.mailcart_service_base_url.rstrip("/")
        self._token = settings.mailcart_service_token

    #R001: Include bearer authorization only when a service token is configured.
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    #R005: Convert message search payload rows into EmailCandidate values and drop rows without message IDs.
    def search_candidates(self, query: str, limit: int = 50) -> list[EmailCandidate]:
        response = requests.get(
            f"{self._base}/v1/messages/search",
            params={"query": query, "limit": limit},
            headers=self._headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("messages", [])
        result: list[EmailCandidate] = []
        for row in rows:
            received_at = self._parse_datetime(row.get("received_at", ""))
            result.append(
                EmailCandidate(
                    message_id=row.get("message_id", ""),
                    subject=row.get("subject", ""),
                    preview=row.get("preview", ""),
                    received_at=received_at,
                    sender=row.get("sender", ""),
                    body_text=row.get("body_text", ""),
                )
            )
        return [item for item in result if item.message_id]

    #R010: Fetch a single Mailcart message envelope (subject/sender/body) so callers can enrich
    #R010: search candidates with the full body. Returns the raw payload dict from Mailcart's
    #R010: GET /v1/messages/{id} endpoint, or an empty dict when the upstream returns a 404
    #R010: (so a per-id miss does not abort enrichment of the whole candidate list).
    def get_message(self, message_id: str) -> dict:
        if not message_id:
            return {}
        response = requests.get(
            f"{self._base}/v1/messages/{message_id}",
            headers=self._headers(),
            timeout=20,
        )
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def move_to_matchy(self, message_id: str) -> bool:
        response = requests.post(
            f"{self._base}/v1/messages/{message_id}/move",
            json={"folder_name": "matchy"},
            headers=self._headers(),
            timeout=20,
        )
        if response.status_code in (200, 204):
            return True
        return False

    def _parse_datetime(self, value: str) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
