from __future__ import annotations

from datetime import datetime, timezone

import requests

from .models import EmailCandidate
from .settings import Settings


class MailcartClient:
    def __init__(self, settings: Settings):
        self._base = settings.mailcart_service_base_url.rstrip("/")
        self._token = settings.mailcart_service_token

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

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
