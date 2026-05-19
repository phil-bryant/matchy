from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


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
    anthropic_api_key_item: str = os.environ.get("MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM", "anthropic_api_key")
    openai_api_key_item: str = os.environ.get("MATCHY_OPENAI_API_KEY_1PSA_ITEM", "openai_api_key")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    anthropic_model: str = os.environ.get("MATCHY_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
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

    def _load_secret_from_1psa(self, secret_ref: str) -> str:
        #R010: Raise clear runtime failures when 1psa cannot return a usable secret.
        output = ""
        command = ["1psa", "-p", secret_ref]
        if secret_ref.startswith("op://"):
            command = ["1psa", "read", secret_ref]
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
        command = ["1psa", "-p", secret_ref]
        if secret_ref.startswith("op://"):
            command = ["1psa", "read", secret_ref]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            if completed.returncode == 0:
                output = completed.stdout.strip()
        except FileNotFoundError:
            output = ""
        return output
