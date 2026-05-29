from __future__ import annotations

from datetime import datetime, timezone
import os
import subprocess
import time

import requests

from .models import EmailCandidate
from .settings import Settings


class MailcartClient:
    def __init__(self, settings: Settings):
        self._base = settings.mailcart_service_base_url.rstrip("/")
        #R015: Mailcart transport must be TLS-only; reject non-https base URLs at initialization.
        if not self._base.lower().startswith("https://"):
            raise RuntimeError("MAILCART_SERVICE_BASE_URL must use https")
        self._token = settings.mailcart_service_token
        configured_timeout = int(getattr(settings, "mailcart_get_message_timeout_seconds", 6) or 6)
        self._message_timeout_seconds = configured_timeout if configured_timeout > 0 else 6
        configured_search_timeout = int(getattr(settings, "mailcart_search_timeout_seconds", 45) or 45)
        self._search_timeout_seconds = configured_search_timeout if configured_search_timeout > 0 else 45
        #R045: Resolve the TLS trust bundle explicitly instead of relying on REQUESTS_CA_BUNDLE being
        #R045: exported in whichever shell launched matchy. Mailcart serves an mkcert-signed localhost
        #R045: certificate whose issuer (the mkcert development CA) is NOT in certifi's default bundle,
        #R045: so every HTTPS call fails verification unless we point requests at the mkcert root CA.
        #R045: Losing that env var across a restart silently broke all search/enrichment calls.
        self._verify = self._resolve_ca_bundle(settings)

    #R045: Determine the CA bundle to verify Mailcart's certificate against. Precedence: explicit
    #R045: MATCHY_MAILCART_CA_BUNDLE override, then REQUESTS_CA_BUNDLE / SSL_CERT_FILE, then the local
    #R045: mkcert development root CA (the common localhost setup), and finally requests' built-in
    #R045: default (certifi) when none of those exist.
    @staticmethod
    def _resolve_ca_bundle(settings: Settings):
        explicit_candidates = [
            getattr(settings, "mailcart_ca_bundle", "") or "",
            os.environ.get("REQUESTS_CA_BUNDLE", "") or "",
            os.environ.get("SSL_CERT_FILE", "") or "",
        ]
        for candidate in explicit_candidates:
            expanded = os.path.expanduser(candidate.strip())
            if expanded and os.path.exists(expanded):
                return expanded
        mkcert_root = os.path.expanduser("~/Library/Application Support/mkcert/rootCA.pem")
        if os.path.exists(mkcert_root):
            return mkcert_root
        try:
            completed = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True, timeout=5)
            if completed.returncode == 0:
                root = os.path.join(completed.stdout.strip(), "rootCA.pem")
                if root and os.path.exists(root):
                    return root
        except (OSError, subprocess.SubprocessError):
            pass
        return True

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
            timeout=self._search_timeout_seconds,
            verify=self._verify,
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
    def get_message(self, message_id: str, timeout_seconds: int | None = None) -> dict:
        if not message_id:
            return {}
        resolved_timeout = self._message_timeout_seconds
        if timeout_seconds is not None:
            candidate_timeout = int(timeout_seconds)
            if candidate_timeout > 0:
                resolved_timeout = candidate_timeout
        response = None
        attempt = 0
        last_error: Exception | None = None
        while attempt < 2:
            attempt += 1
            try:
                response = requests.get(
                    f"{self._base}/v1/messages/{message_id}",
                    headers=self._headers(),
                    timeout=resolved_timeout,
                    verify=self._verify,
                )
                if response.status_code == 404:
                    return {}
                if response.status_code in {502, 503, 504} and attempt < 2:
                    time.sleep(0.15)
                    continue
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.15)
                    continue
                raise
        if response is None:
            if last_error is not None:
                raise last_error
            return {}
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def move_to_matchy(self, message_id: str) -> bool:
        response = requests.post(
            f"{self._base}/v1/messages/{message_id}/move",
            json={"folder_name": "matchy"},
            headers=self._headers(),
            timeout=20,
            verify=self._verify,
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
