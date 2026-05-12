from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    teller_db_host: str = os.environ.get("TELLER_DB_HOST", "localhost")
    teller_db_port: int = int(os.environ.get("TELLER_DB_PORT", "5432"))
    teller_db_name: str = os.environ.get("TELLER_DB_NAME", "prod")
    teller_db_user: str = os.environ.get("TELLER_DB_USER", "teller")
    teller_db_password: str = os.environ.get("TELLER_DB_PASSWORD", "")
    email_service_base_url: str = os.environ.get("EMAIL_SERVICE_BASE_URL", "http://127.0.0.1:8788")
    email_service_token: str = os.environ.get("EMAIL_SERVICE_TOKEN", "")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    openai_model: str = os.environ.get("MATCHY_OPENAI_MODEL", "gpt-4.1-mini")
    auto_confirm_threshold: float = float(os.environ.get("MATCHY_AUTO_CONFIRM_THRESHOLD", "0.90"))
    write_enabled: bool = os.environ.get("MATCHY_WRITE_ENABLED", "true").lower() == "true"
    email_move_enabled: bool = os.environ.get("MATCHY_EMAIL_MOVE_ENABLED", "false").lower() == "true"
