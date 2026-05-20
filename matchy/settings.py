from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

_ONEPSA_ITEM_REF_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
_ONEPSA_OP_REF_PATTERN = re.compile(r"^op://[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class Settings:
    teller_db_password_item: str = os.environ.get("TELLER_DB_PASSWORD_1PSA_ITEM", "localhost_postgres_teller")
    teller_db_host: str = os.environ.get("TELLER_DB_HOST", "localhost")
    teller_db_port: int = int(os.environ.get("TELLER_DB_PORT", "5432"))
    teller_db_name: str = os.environ.get("TELLER_DB_NAME", "prod")
    teller_db_user: str = os.environ.get("TELLER_DB_USER", "teller")
    teller_db_password: str = os.environ.get("TELLER_DB_PASSWORD", "")
    mailcart_service_base_url: str = os.environ.get("MAILCART_SERVICE_BASE_URL", "http://127.0.0.1:8788")
    mailcart_service_token: str = os.environ.get("MAILCART_SERVICE_TOKEN", "")
    #R030: Enrich search candidates with the full Mailcart message body before scoring so amount/keyword
    #R030: hints can match against the email body (not just bodyPreview). Disable when callers want the
    #R030: legacy preview-only behavior for performance or determinism reasons. Empty env var values
    #R030: collapse to the default so `MATCHY_MAILCART_BODY_ENRICHMENT=""` behaves the same as unset.
    mailcart_body_enrichment_enabled: bool = (
        (os.environ.get("MATCHY_MAILCART_BODY_ENRICHMENT") or "true").strip().lower() == "true"
    )
    mailcart_body_enrichment_limit: int = int(
        (os.environ.get("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT") or "75").strip() or "75"
    )
    anthropic_api_key_item: str = os.environ.get("MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM", "anthropic_api_key")
    openai_api_key_item: str = os.environ.get("MATCHY_OPENAI_API_KEY_1PSA_ITEM", "openai_api_key")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    #R035: Default Anthropic model. The `-latest` aliases (e.g., `claude-3-5-sonnet-latest`) were
    #R035: deprecated by Anthropic and now return 404 when called. Pin a dated/stable model id so the
    #R035: AI ranker keeps working out of the box; callers can override via `MATCHY_ANTHROPIC_MODEL`.
    #R035: Empty env values collapse to the default so `MATCHY_ANTHROPIC_MODEL=""` behaves like unset.
    anthropic_model: str = (os.environ.get("MATCHY_ANTHROPIC_MODEL") or "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"
    openai_model: str = os.environ.get("MATCHY_OPENAI_MODEL", "gpt-4.1-mini")
    auto_confirm_threshold: float = float(os.environ.get("MATCHY_AUTO_CONFIRM_THRESHOLD", "0.90"))
    write_enabled: bool = os.environ.get("MATCHY_WRITE_ENABLED", "true").lower() == "true"
    email_move_enabled: bool = os.environ.get("MATCHY_EMAIL_MOVE_ENABLED", "false").lower() == "true"

    def __post_init__(self) -> None:
        object.__setattr__(self, "teller_db_password", self._resolve_teller_db_password())
        object.__setattr__(self, "anthropic_api_key", self._resolve_optional_api_key(self.anthropic_api_key, self.anthropic_api_key_item))
        object.__setattr__(self, "openai_api_key", self._resolve_optional_api_key(self.openai_api_key, self.openai_api_key_item))

    def _resolve_teller_db_password(self) -> str:
        #R001: Resolve Teller DB password from 1psa using default item name when no override is provided.
        secret_ref = os.environ.get("TELLER_DB_PASSWORD_1PSA_REF", "").strip()
        if not secret_ref:
            secret_ref = self.teller_db_password_item
        #R005: Support both item-name and op:// references in 1psa lookups.
        password = self._load_secret_from_1psa(secret_ref)
        return password

    def _resolve_optional_api_key(self, env_value: str, item_name: str) -> str:
        #R015: Resolve Anthropic (primary) and OpenAI (fallback) AI keys from 1psa with env-var overrides, tolerating absent items.
        resolved = env_value.strip()
        if not resolved and item_name.strip():
            resolved = self._load_optional_secret_from_1psa(item_name.strip())
        return resolved

    def _validate_1psa_secret_ref(self, secret_ref: str) -> str:
        candidate = secret_ref.strip()
        if not candidate:
            raise ValueError("1psa secret reference must not be empty")
        if candidate.startswith("op://"):
            if not _ONEPSA_OP_REF_PATTERN.fullmatch(candidate):
                raise ValueError(f"invalid op:// 1psa reference: {candidate!r}")
            return candidate
        if not _ONEPSA_ITEM_REF_PATTERN.fullmatch(candidate):
            raise ValueError(f"invalid 1psa item reference: {candidate!r}")
        return candidate

    def _load_secret_from_1psa(self, secret_ref: str) -> str:
        #R010: Raise clear runtime failures when 1psa cannot return a usable secret.
        output = ""
        validated_ref = self._validate_1psa_secret_ref(secret_ref)
        command = ["1psa", "-p", validated_ref]
        if validated_ref.startswith("op://"):
            command = ["1psa", "read", validated_ref]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            output = completed.stdout.strip()
        except FileNotFoundError as exc:
            raise RuntimeError("TELLER_DB_PASSWORD_1PSA_REF is set but 1psa is not installed or not on PATH") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() if exc.stderr else "unknown 1psa error"
            if ("Forbidden" in detail or "auth/start" in detail) and os.environ.get("OP_SERVICE_ACCOUNT_TOKEN", "").strip():
                raise RuntimeError(
                    "1psa authentication failed for OP_SERVICE_ACCOUNT_TOKEN; verify token validity and secret access."
                ) from exc
            raise RuntimeError(f"1psa failed to resolve TELLER_DB_PASSWORD_1PSA_REF: {detail}") from exc
        if not output:
            raise RuntimeError("1psa returned an empty secret for TELLER_DB_PASSWORD_1PSA_REF")
        return output

    def _load_optional_secret_from_1psa(self, secret_ref: str) -> str:
        #R015: Optional 1psa secrets resolve to empty string when 1psa is missing, errors, or returns nothing.
        output = ""
        validated_ref = self._validate_1psa_secret_ref(secret_ref)
        command = ["1psa", "-p", validated_ref]
        if validated_ref.startswith("op://"):
            command = ["1psa", "read", validated_ref]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            if completed.returncode == 0:
                output = completed.stdout.strip()
        except FileNotFoundError:
            output = ""
        return output
