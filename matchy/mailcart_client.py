from __future__ import annotations

from datetime import datetime, timezone
import os
import subprocess
import time
from urllib.parse import urlparse

import requests

from .models import EmailCandidate
from .settings import Settings


class MailcartClient:
    def __init__(self, settings: Settings):
        self._base = settings.mailcart_service_base_url.rstrip("/")
        #R015: Mailcart transport must be TLS-only; reject non-https/invalid base URLs at initialization.
        self._validate_base_url(self._base)
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
        configured_health_timeout = int(getattr(settings, "mailcart_startup_healthcheck_timeout_seconds", 2) or 2)
        self._startup_healthcheck_timeout_seconds = configured_health_timeout if configured_health_timeout > 0 else 2

    @staticmethod
    def _validate_base_url(base_url: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme.lower() != "https":
            raise RuntimeError("MAILCART_SERVICE_BASE_URL must use https")
        if not parsed.netloc:
            raise RuntimeError("MAILCART_SERVICE_BASE_URL must include host and port")

    #R045: Determine the CA bundle to verify Mailcart's certificate against. Precedence: explicit
    #R045: MATCHY_MAILCART_CA_BUNDLE override, then REQUESTS_CA_BUNDLE / SSL_CERT_FILE, then the local
    #R045: mkcert development root CA (the common localhost setup), and finally requests' built-in
    #R045: default (certifi) when none of those exist.
    @staticmethod
    def _resolve_ca_bundle(settings: Settings):
        explicit_override = str(getattr(settings, "mailcart_ca_bundle", "") or "").strip()
        if explicit_override:
            expanded_override = os.path.expanduser(explicit_override)
            if os.path.exists(expanded_override):
                return expanded_override
            raise RuntimeError(
                f"MATCHY_MAILCART_CA_BUNDLE points to a missing file: {expanded_override}"
            )
        requests_ca_bundle = str(os.environ.get("REQUESTS_CA_BUNDLE", "") or "").strip()
        if requests_ca_bundle:
            expanded_requests_ca = os.path.expanduser(requests_ca_bundle)
            if os.path.exists(expanded_requests_ca):
                return expanded_requests_ca
            raise RuntimeError(f"REQUESTS_CA_BUNDLE points to a missing file: {expanded_requests_ca}")
        ssl_cert_file = str(os.environ.get("SSL_CERT_FILE", "") or "").strip()
        if ssl_cert_file:
            expanded_ssl_cert = os.path.expanduser(ssl_cert_file)
            if os.path.exists(expanded_ssl_cert):
                return expanded_ssl_cert
            raise RuntimeError(f"SSL_CERT_FILE points to a missing file: {expanded_ssl_cert}")
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

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self._base}{normalized_path}"

    #R050: Build deterministic transport diagnostics used by startup preflight failures so operators see
    #R050: exactly which base URL and verify bundle requests attempted to use.
    def _transport_context(self) -> str:
        verify_repr = self._verify if isinstance(self._verify, str) else "default-cert-store"
        return f"base_url={self._base} verify={verify_repr}"

    def _request_get(self, path: str, *, timeout: int, params: dict | None = None) -> requests.Response:
        return requests.get(
            self._build_url(path),
            params=params or {},
            headers=self._headers(),
            timeout=timeout,
            verify=self._verify,
        )

    def _request_post(self, path: str, *, timeout: int, payload: dict) -> requests.Response:
        return requests.post(
            self._build_url(path),
            json=payload,
            headers=self._headers(),
            timeout=timeout,
            verify=self._verify,
        )

    #R050: Probe Mailcart /health with the same URL builder, headers, timeout, and TLS verify bundle used
    #R050: by runtime search/get-message requests so startup catches transport misconfiguration early.
    def startup_preflight_healthcheck(self) -> None:
        try:
            response = self._request_get("/health", timeout=self._startup_healthcheck_timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                "Mailcart startup preflight failed. "
                f"Check MAILCART_SERVICE_BASE_URL scheme and TLS verify bundle. {self._transport_context()} error={exc}"
            ) from exc

    #R001: Include bearer authorization only when a service token is configured.
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    #R005: Convert message search payload rows into EmailCandidate values and drop rows without message IDs.
    def search_candidates(self, query: str, limit: int = 50) -> list[EmailCandidate]:
        response = self._request_get(
            "/v1/messages/search",
            params={"query": query, "limit": limit},
            timeout=self._search_timeout_seconds,
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
                    self._build_url(f"/v1/messages/{message_id}"),
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
        response = self._request_post(
            f"/v1/messages/{message_id}/move",
            payload={"folder_name": "matchy"},
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
