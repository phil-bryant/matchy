from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Mapping

_ONEPSA_ITEM_REF_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
_ONEPSA_ITEM_FIELD_REF_PATTERN = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
_ONEPSA_OP_REF_PATTERN = re.compile(r"^op://[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


#R882: Resolve the active teller DB profile target for backend-aware startup.
def _teller_profile_target() -> str:
    try:
        from teller.teller_db_profile import resolve_profile

        return resolve_profile().target
    except Exception:  # noqa: BLE001 - missing teller/profile keeps postgres-era behavior
        return ""


#R880: Emit optional startup phase timing logs when MATCHY_STARTUP_LOG is enabled.
def _startup_log(start_time_seconds: float, phase: str, details: str = "") -> None:
    enabled = os.environ.get("MATCHY_STARTUP_LOG", "false").strip().lower() == "true"
    if enabled:
        elapsed_seconds = perf_counter() - start_time_seconds
        suffix = f" | {details}" if details else ""
        print(f"[matchy-startup +{elapsed_seconds:7.3f}s] {phase}{suffix}", flush=True)


@dataclass(frozen=True)
class Settings:
    teller_db_password_item: str = os.environ.get("TELLER_DB_PASSWORD_1PSA_ITEM", "localhost_postgres_teller")
    teller_db_host: str = os.environ.get("TELLER_DB_HOST", "")
    teller_db_port: int = int((os.environ.get("TELLER_DB_PORT") or "0").strip() or "0")
    teller_db_name: str = os.environ.get("TELLER_DB_NAME", "")
    teller_db_user: str = os.environ.get("TELLER_DB_USER", "")
    teller_db_password: str = os.environ.get("TELLER_DB_PASSWORD", "")
    mailcart_service_base_url: str = os.environ.get("MAILCART_SERVICE_BASE_URL", "https://127.0.0.1:8788")
    mailcart_service_token: str = os.environ.get("MAILCART_SERVICE_TOKEN", "")
    matchy_api_auth_token: str = os.environ.get("MATCHY_API_AUTH_TOKEN", "").strip()
    #R905: Enrich search candidates with the full Mailcart message body before scoring so amount/keyword
    #R905: hints can match against body content, with env-controlled defaults and overrides.
    mailcart_body_enrichment_enabled: bool = (
        (os.environ.get("MATCHY_MAILCART_BODY_ENRICHMENT") or "true").strip().lower() == "true"
    )
    mailcart_body_enrichment_limit: int = int(
        (os.environ.get("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT") or "75").strip() or "75"
    )
    mailcart_body_enrichment_timeout_seconds: int = int(
        (os.environ.get("MATCHY_MAILCART_BODY_ENRICHMENT_TIMEOUT_SECONDS") or "12").strip() or "12"
    )
    mailcart_body_enrichment_max_workers: int = int(
        (os.environ.get("MATCHY_MAILCART_BODY_ENRICHMENT_MAX_WORKERS") or "12").strip() or "12"
    )
    mailcart_get_message_timeout_seconds: int = int(
        (os.environ.get("MATCHY_MAILCART_GET_MESSAGE_TIMEOUT_SECONDS") or "3").strip() or "3"
    )
    mailcart_failure_cooldown_seconds: int = int(
        (os.environ.get("MATCHY_MAILCART_FAILURE_COOLDOWN_SECONDS") or "15").strip() or "15"
    )
    mailcart_search_date_window_days: int = int(
        (os.environ.get("MATCHY_MAILCART_SEARCH_DATE_WINDOW_DAYS") or "45").strip() or "45"
    )
    #R915: Expose configurable Mailcart search timeout defaults to reduce false timeout failures.
    mailcart_search_timeout_seconds: int = int(
        (os.environ.get("MATCHY_MAILCART_SEARCH_TIMEOUT_SECONDS") or "45").strip() or "45"
    )
    #R915: Expose optional explicit CA bundle path for Mailcart TLS verification.
    mailcart_ca_bundle: str = os.environ.get("MATCHY_MAILCART_CA_BUNDLE", "")
    #R915: Optionally run a single Mailcart /health probe at startup to fail fast on transport misconfiguration.
    mailcart_startup_healthcheck_enabled: bool = (
        (os.environ.get("MATCHY_MAILCART_STARTUP_HEALTHCHECK") or "true").strip().lower() == "true"
    )
    mailcart_startup_healthcheck_timeout_seconds: int = int(
        (os.environ.get("MATCHY_MAILCART_STARTUP_HEALTHCHECK_TIMEOUT_SECONDS") or "2").strip() or "2"
    )
    anthropic_api_key_item: str = os.environ.get("MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM", "anthropic_api_key")
    openai_api_key_item: str = os.environ.get("MATCHY_OPENAI_API_KEY_1PSA_ITEM", "openai_api_key")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    #R910: Default Anthropic model is pinned to a stable id and remains env-overridable.
    anthropic_model: str = (os.environ.get("MATCHY_ANTHROPIC_MODEL") or "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"
    openai_model: str = os.environ.get("MATCHY_OPENAI_MODEL", "gpt-4.1-mini")
    auto_confirm_threshold: float = float(os.environ.get("MATCHY_AUTO_CONFIRM_THRESHOLD", "0.90"))
    write_enabled: bool = os.environ.get("MATCHY_WRITE_ENABLED", "true").lower() == "true"
    email_move_enabled: bool = os.environ.get("MATCHY_EMAIL_MOVE_ENABLED", "false").lower() == "true"
    near_duplicate_max_hamming_distance: int = int(
        (os.environ.get("MATCHY_NEAR_DUPLICATE_MAX_HAMMING_DISTANCE") or "0").strip() or "0"
    )
    #R919: Expose CLDR currencies cache path/refresh controls with env overrides.
    cldr_currencies_cache_path: str = os.environ.get(
        "MATCHY_CLDR_CURRENCIES_CACHE_PATH",
        str(Path.home() / ".cache" / "matchy" / "cldr-currencies-en.json"),
    )
    cldr_currencies_refresh_enabled: bool = (
        os.environ.get("MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED", "true").lower() == "true"
    )
    cldr_currencies_refresh_timeout_seconds: int = int(os.environ.get("MATCHY_CLDR_CURRENCIES_REFRESH_TIMEOUT_SECONDS", "5"))

    #R880: Initialize runtime settings, then resolve DB and API secrets before service startup.
    def __post_init__(self) -> None:
        startup_started_at = perf_counter()
        _startup_log(startup_started_at, "settings-init-enter")
        object.__setattr__(
            self,
            "cldr_currencies_cache_path",
            os.environ.get("MATCHY_CLDR_CURRENCIES_CACHE_PATH", self.cldr_currencies_cache_path),
        )
        object.__setattr__(
            self,
            "cldr_currencies_refresh_enabled",
            os.environ.get(
                "MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED",
                str(self.cldr_currencies_refresh_enabled),
            ).lower() == "true",
        )
        object.__setattr__(
            self,
            "cldr_currencies_refresh_timeout_seconds",
            int(os.environ.get(
                "MATCHY_CLDR_CURRENCIES_REFRESH_TIMEOUT_SECONDS",
                str(self.cldr_currencies_refresh_timeout_seconds),
            )),
        )
        object.__setattr__(
            self,
            "matchy_api_auth_token",
            os.environ.get("MATCHY_API_AUTH_TOKEN", self.matchy_api_auth_token).strip(),
        )
        resolved_mailcart_service_token = self._resolve_mailcart_service_token()
        object.__setattr__(self, "mailcart_service_token", resolved_mailcart_service_token)
        if resolved_mailcart_service_token and not os.environ.get("MAILCART_SERVICE_TOKEN", "").strip():
            os.environ["MAILCART_SERVICE_TOKEN"] = resolved_mailcart_service_token
        object.__setattr__(
            self,
            "write_enabled",
            os.environ.get("MATCHY_WRITE_ENABLED", str(self.write_enabled)).strip().lower() == "true",
        )
        resolve_db_started_at = perf_counter()
        #R882: SQLite profile targets need no Postgres credentials; the repository
        #R882: binds to teller's profile-driven engine, which resolves the
        #R882: SQLCipher path/key itself.
        if _teller_profile_target() == "sqlite":
            _startup_log(startup_started_at, "settings-db-config-skipped", "target=sqlite")
        else:
            teller_db_config = self._resolve_teller_db_config()
            _startup_log(startup_started_at, "settings-db-config-resolved", f"phase_elapsed={perf_counter() - resolve_db_started_at:7.3f}s")
            object.__setattr__(self, "teller_db_host", teller_db_config["host"])
            object.__setattr__(self, "teller_db_port", teller_db_config["port"])
            object.__setattr__(self, "teller_db_name", teller_db_config["database"])
            object.__setattr__(self, "teller_db_user", teller_db_config["username"])
            object.__setattr__(self, "teller_db_password", teller_db_config["password"])
        anthropic_started_at = perf_counter()
        object.__setattr__(self, "anthropic_api_key", self._resolve_optional_api_key(self.anthropic_api_key, self.anthropic_api_key_item))
        _startup_log(startup_started_at, "settings-anthropic-key-resolved", f"phase_elapsed={perf_counter() - anthropic_started_at:7.3f}s")
        openai_started_at = perf_counter()
        object.__setattr__(self, "openai_api_key", self._resolve_optional_api_key(self.openai_api_key, self.openai_api_key_item))
        _startup_log(startup_started_at, "settings-openai-key-resolved", f"phase_elapsed={perf_counter() - openai_started_at:7.3f}s")
        _startup_log(startup_started_at, "settings-init-complete")

    def _resolve_teller_db_config(self) -> dict[str, str | int]:
        #R880: Resolve all Teller DB fields from 1psa first, then ~/.env as a single fallback.
        source_details = ""
        resolved = self._resolve_db_config_from_1psa()
        if not resolved:
            source_details = "1psa lookup did not return a complete DB configuration."
            resolved = self._resolve_db_config_from_home_env()
            if not resolved:
                message = (
                    "Unable to resolve Teller DB config. First source (1psa) failed and fallback "
                    "(~/.env) is missing/incomplete. Required fields: username,password,host,port,database."
                )
                if source_details:
                    message = f"{message} Detail: {source_details}"
                raise RuntimeError(message)
        return resolved

    #R880: Preserve backward-compatible password helper behavior for existing call sites.
    def _resolve_teller_db_password(self) -> str:
        # Backward-compatible helper retained for tests and call sites that patch this method.
        resolved = self._resolve_teller_db_config()
        return str(resolved["password"])

    def _resolve_db_config_from_1psa(self) -> dict[str, str | int]:
        #R885: Support configurable 1psa item-name and op:// references for DB field resolution.
        resolved: dict[str, str | int] = {}
        raw_values: dict[str, str] = {}
        secret_ref = os.environ.get("TELLER_DB_PASSWORD_1PSA_REF", "").strip()
        if not secret_ref:
            secret_ref = self.teller_db_password_item
        if secret_ref:
            item_values = self._load_db_item_values_from_1psa(secret_ref)
            raw_values = item_values
            if item_values:
                resolved = self._coerce_db_config(raw_values)
        return resolved

    #R890: Fall back to ~/.env for DB settings only when 1psa cannot produce a complete config.
    def _resolve_db_config_from_home_env(self) -> dict[str, str | int]:
        resolved: dict[str, str | int] = {}
        env_values = self._read_home_env_file()
        raw_values: dict[str, str] = {}
        raw_values["username"] = env_values.get("username", env_values.get("TELLER_DB_USER", ""))
        raw_values["password"] = env_values.get("password", env_values.get("TELLER_DB_PASSWORD", ""))
        raw_values["host"] = env_values.get("host", env_values.get("TELLER_DB_HOST", ""))
        raw_values["port"] = env_values.get("port", env_values.get("TELLER_DB_PORT", ""))
        raw_values["database"] = env_values.get("database", env_values.get("TELLER_DB_NAME", ""))
        if raw_values["username"] and raw_values["password"] and raw_values["host"] and raw_values["port"] and raw_values["database"]:
            resolved = self._coerce_db_config(raw_values)
        return resolved

    #R885: Resolve DB credential fields from a 1psa item or op:// reference.
    def _load_db_item_values_from_1psa(self, secret_ref: str) -> dict[str, str]:
        started_at = perf_counter()
        values: dict[str, str] = {}
        refs = self._build_1psa_db_field_refs(secret_ref)
        raw: dict[str, str] = {}
        if not secret_ref.startswith("op://"):
            raw = self._load_multiple_fields_from_1psa_item(secret_ref)
        if not raw:
            raw["username"] = self._load_optional_secret_from_1psa(refs["username"])
            raw["password"] = self._load_optional_secret_from_1psa(refs["password"])
            raw["host"] = self._load_optional_secret_from_1psa(refs["host"])
            raw["port"] = self._load_optional_secret_from_1psa(refs["port"])
            raw["database"] = self._load_optional_secret_from_1psa(refs["database"])
        username = raw.get("username", "")
        password = raw.get("password", "")
        host = raw.get("host", "")
        port = raw.get("port", "")
        database = raw.get("database", "")
        if username and password and host and port and database:
            values["username"] = username
            values["password"] = password
            values["host"] = host
            values["port"] = port
            values["database"] = database
        _startup_log(started_at, "settings-1psa-db-fields-loaded", f"source={secret_ref}")
        return values

    #R885: Attempt multi-field 1psa fetch for DB credentials and parse supported output formats.
    def _load_multiple_fields_from_1psa_item(self, item_ref: str) -> dict[str, str]:
        started_at = perf_counter()
        values: dict[str, str] = {}
        fields = ["username", "password", "host", "port", "database"]
        command = ["1psa", "-m", item_ref]
        command.extend(fields)
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            if completed.returncode == 0:
                values = self._parse_1psa_multi_output(completed.stdout, fields)
            _startup_log(
                started_at,
                "settings-1psa-multi-lookup-complete",
                f"item={item_ref} rc={completed.returncode} parsed_fields={len(values)}",
            )
        except FileNotFoundError:
            values = {}
            _startup_log(started_at, "settings-1psa-multi-lookup-complete", f"item={item_ref} missing_binary=true")
        except Exception as exc:
            values = {}
            _startup_log(started_at, "settings-1psa-multi-lookup-complete", f"item={item_ref} error={type(exc).__name__}")
        return values

    #R885: Parse 1psa multi-field output in positional or key-value formats.
    def _parse_1psa_multi_output(self, output: str, fields: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        has_key_value_lines = any(("=" in line) or (":" in line) for line in lines)
        if len(lines) == len(fields) and not has_key_value_lines:
            index = 0
            while index < len(fields):
                values[fields[index]] = lines[index].strip().strip('"').strip("'")
                index += 1
        if len(values) != len(fields):
            values = {}
            for line in lines:
                if "=" in line:
                    key, raw_value = line.split("=", 1)
                    clean_key = key.strip().lower()
                    if clean_key in fields:
                        values[clean_key] = raw_value.strip().strip('"').strip("'")
                if ":" in line:
                    key, raw_value = line.split(":", 1)
                    clean_key = key.strip().lower()
                    if clean_key in fields:
                        values[clean_key] = raw_value.strip().strip('"').strip("'")
        if len(values) != len(fields):
            values = {}
        return values

    #R885: Build 1psa field references for item-name and op:// secret references.
    def _build_1psa_db_field_refs(self, secret_ref: str) -> dict[str, str]:
        refs: dict[str, str] = {}
        if secret_ref.startswith("op://"):
            validated_ref = self._validate_1psa_secret_ref(secret_ref)
            ref_parts = validated_ref.split("/")
            item_ref = "/".join(ref_parts[0:4])
            refs["username"] = f"{item_ref}/username"
            refs["password"] = f"{item_ref}/password"
            refs["host"] = f"{item_ref}/host"
            refs["port"] = f"{item_ref}/port"
            refs["database"] = f"{item_ref}/database"
        if not secret_ref.startswith("op://"):
            validated_item = self._validate_1psa_secret_ref(secret_ref)
            refs["username"] = f"{validated_item}/username"
            refs["password"] = f"{validated_item}/password"
            refs["host"] = f"{validated_item}/host"
            refs["port"] = f"{validated_item}/port"
            refs["database"] = f"{validated_item}/database"
        return refs

    #R890: Validate and coerce resolved DB settings, rejecting non-integer ports or missing fields.
    def _coerce_db_config(self, raw_values: Mapping[str, str]) -> dict[str, str | int]:
        port_raw = raw_values.get("port", "").strip()
        if not port_raw.isdigit():
            raise RuntimeError("Resolved Teller DB port is not a valid integer.")
        resolved: dict[str, str | int] = {}
        resolved["username"] = raw_values.get("username", "").strip()
        resolved["password"] = raw_values.get("password", "").strip()
        resolved["host"] = raw_values.get("host", "").strip()
        resolved["port"] = int(port_raw)
        resolved["database"] = raw_values.get("database", "").strip()
        if not (resolved["username"] and resolved["password"] and resolved["host"] and resolved["database"]):
            raise RuntimeError("Resolved Teller DB config is missing one or more required fields.")
        return resolved

    #R890: Parse ~/.env key-value lines (including export syntax) for DB fallback fields.
    def _read_home_env_file(self) -> dict[str, str]:
        values: dict[str, str] = {}
        env_path = Path.home() / ".env"
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            index = 0
            while index < len(lines):
                raw_line = lines[index]
                stripped = raw_line.strip()
                if stripped and not stripped.startswith("#"):
                    normalized = stripped
                    if normalized.startswith("export "):
                        normalized = normalized[len("export ") :].strip()
                    if "=" in normalized:
                        key, value = normalized.split("=", 1)
                        clean_key = key.strip()
                        clean_value = value.strip().strip('"').strip("'")
                        if clean_key:
                            values[clean_key] = clean_value
                index += 1
        return values

    def _resolve_optional_api_key(self, env_value: str, item_name: str) -> str:
        #R895: Resolve Anthropic/OpenAI API keys with env-var precedence and tolerant 1psa fallback.
        resolved = env_value.strip()
        if not resolved and item_name.strip():
            resolved = self._load_optional_secret_from_1psa(item_name.strip())
        return resolved

    #R880: Resolve Mailcart service token with env precedence and ~/.env fallback for startup wiring.
    def _resolve_mailcart_service_token(self) -> str:
        token = (os.environ.get("MAILCART_SERVICE_TOKEN", "") or self.mailcart_service_token or "").strip()
        if token:
            return token
        for env_key in ("CLASSY_WRITE_TOKEN", "TELLER_CLASSIFIER_WRITE_TOKEN"):
            candidate = os.environ.get(env_key, "").strip()
            if candidate:
                return candidate
        env_values = self._read_home_env_file()
        for env_key in ("MAILCART_SERVICE_TOKEN", "CLASSY_WRITE_TOKEN", "TELLER_CLASSIFIER_WRITE_TOKEN"):
            candidate = env_values.get(env_key, "").strip()
            if candidate:
                return candidate
        return ""

    #R885: Validate supported 1psa secret reference formats before invoking 1psa commands.
    def _validate_1psa_secret_ref(self, secret_ref: str) -> str:
        candidate = secret_ref.strip()
        if not candidate:
            raise ValueError("1psa secret reference must not be empty")
        if candidate.startswith("op://"):
            if not _ONEPSA_OP_REF_PATTERN.fullmatch(candidate):
                raise ValueError(f"invalid op:// 1psa reference: {candidate!r}")
            return candidate
        if _ONEPSA_ITEM_REF_PATTERN.fullmatch(candidate):
            return candidate
        if _ONEPSA_ITEM_FIELD_REF_PATTERN.fullmatch(candidate):
            return candidate
        if not _ONEPSA_ITEM_REF_PATTERN.fullmatch(candidate):
            raise ValueError(f"invalid 1psa item reference: {candidate!r}")
        return candidate

    def _load_secret_from_1psa(self, secret_ref: str) -> str:
        #R895: Raise explicit runtime failures when required 1psa secrets cannot be resolved.
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
        #R895: Optional 1psa secrets resolve to empty string when 1psa is missing or returns errors.
        started_at = perf_counter()
        output = ""
        validated_ref = ""
        try:
            validated_ref = self._validate_1psa_secret_ref(secret_ref)
        except ValueError:
            validated_ref = ""
        if validated_ref:
            command = self._build_1psa_command(validated_ref)
            try:
                completed = subprocess.run(command, check=False, capture_output=True, text=True)
                if completed.returncode == 0:
                    output = completed.stdout.strip()
                _startup_log(
                    started_at,
                    "settings-1psa-lookup-complete",
                    f"ref={validated_ref} rc={completed.returncode} value_present={str(bool(output)).lower()}",
                )
            except FileNotFoundError:
                output = ""
                _startup_log(started_at, "settings-1psa-lookup-complete", f"ref={validated_ref} missing_binary=true")
        if not validated_ref:
            _startup_log(started_at, "settings-1psa-lookup-skipped", f"ref={secret_ref}")
        return output

    #R895: Select the correct 1psa invocation style for item refs, op:// refs, and item/field refs.
    def _build_1psa_command(self, validated_ref: str) -> list[str]:
        command = ["1psa", "-p", validated_ref]
        if validated_ref.startswith("op://"):
            command = ["1psa", "read", validated_ref]
        if (not validated_ref.startswith("op://")) and "/" in validated_ref:
            item_name, field_name = validated_ref.split("/", 1)
            command = ["1psa", "-f", item_name, field_name]
        return command
