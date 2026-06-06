#R001: Python test lane coverage for default 1psa teller DB config resolution.
#R005: Python test lane coverage for 1psa reference overrides.
#R010: Python test lane coverage for 1psa and ~/.env fallback failure handling.
#R015: Python test lane coverage for AI key resolution.
#R030: Python test lane coverage for mailcart body enrichment defaults.
#R035: Python test lane coverage for anthropic model defaults.
#R050: Python test lane coverage for CLDR currencies cache startup settings.

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

import matchy.settings as settings_module
from matchy.settings import Settings


class CompletedProcess:
    #R001: Test helper supports this requirement-focused scenario.
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


#R001: Test helper supports this requirement-focused scenario.
def _install_run_stub(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    #R001: Test helper supports this requirement-focused scenario.
    def fake_run(command, **kwargs: Any):
        return handler(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)


#R001: Test helper supports this requirement-focused scenario.
def _clear_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELLER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("TELLER_DB_HOST", raising=False)
    monkeypatch.delenv("TELLER_DB_PORT", raising=False)
    monkeypatch.delenv("TELLER_DB_NAME", raising=False)
    monkeypatch.delenv("TELLER_DB_USER", raising=False)
    monkeypatch.delenv("TELLER_DB_PASSWORD_1PSA_REF", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


#R001: Test helper supports this requirement-focused scenario.
def _optional_miss_handler(command, **kwargs):
    requested_ref = _requested_secret_ref(command)
    if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
        if requested_ref in (
            "localhost_postgres_teller/username",
            "localhost_postgres_teller/password",
            "localhost_postgres_teller/host",
            "localhost_postgres_teller/port",
            "localhost_postgres_teller/database",
        ):
            field = requested_ref.split("/")[-1]
            if field == "username":
                return CompletedProcess(0, "teller\n")
            if field == "password":
                return CompletedProcess(0, "fixture-default\n")
            if field == "host":
                return CompletedProcess(0, "localhost\n")
            if field == "port":
                return CompletedProcess(0, "5432\n")
            if field == "database":
                return CompletedProcess(0, "teller\n")
        return CompletedProcess(5, "", "item not found")
    raise AssertionError(f"unexpected command: {command}")


#R001: Test helper supports this requirement-focused scenario.
def _reload_settings_class(monkeypatch: pytest.MonkeyPatch):
    importlib.reload(settings_module)
    return settings_module.Settings


#R001: Test helper supports this requirement-focused scenario.
def _settings_attr(settings: Settings, *name_parts: str) -> str:
    return getattr(settings, "".join(name_parts))


#R001: Test helper supports this requirement-focused scenario.
def _requested_secret_ref(command: list[str]) -> str:
    requested = ""
    if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
        requested = command[-1]
    if command[0:2] == ["1psa", "-f"]:
        requested = f"{command[2]}/{command[3]}"
    return requested


#R001: Test helper supports this requirement-focused scenario.
def _db_config(settings: Settings) -> tuple[str, str, str, int, str]:
    return (
        settings.teller_db_user,
        settings.teller_db_password,
        settings.teller_db_host,
        settings.teller_db_port,
        settings.teller_db_name,
    )


def test_loads_teller_db_config_from_default_1psa_item_when_no_refs_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    #R001: Default 1psa item resolves full teller DB config without DB env vars.
    #R001-T01: Python test lane exists for default teller DB config requirement.
    _clear_secret_env(monkeypatch)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    assert _db_config(Settings()) == ("teller", "fixture-default", "localhost", 5432, "teller")


def test_loads_teller_db_config_through_1psa_item_reference_override(monkeypatch: pytest.MonkeyPatch) -> None:
    #R005: Item-name override resolves full DB config through 1psa -p item/field.
    #R005-T01: Python test lane exists for item-name override requirement.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("TELLER_DB_PASSWORD_1PSA_REF", "custom_item")

    #R005: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        field_ref = _requested_secret_ref(command)
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            if field_ref == "custom_item/username":
                return CompletedProcess(0, "custom-user\n")
            if field_ref == "custom_item/password":
                return CompletedProcess(0, "custom-password\n")
            if field_ref == "custom_item/host":
                return CompletedProcess(0, "127.0.0.1\n")
            if field_ref == "custom_item/port":
                return CompletedProcess(0, "15432\n")
            if field_ref == "custom_item/database":
                return CompletedProcess(0, "custom-db\n")
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert _db_config(Settings()) == ("custom-user", "custom-password", "127.0.0.1", 15432, "custom-db")


def test_loads_teller_db_config_through_1psa_read_for_op_references(monkeypatch: pytest.MonkeyPatch) -> None:
    #R005: op:// references resolve full DB config through 1psa read.
    #R005-T02: Python test lane exists for op:// reference requirement.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token-ok")
    monkeypatch.setenv("TELLER_DB_PASSWORD_1PSA_REF", "op://vault/item/password")

    #R005: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] == ["1psa", "read"]:
            field_ref = _requested_secret_ref(command)
            if field_ref == "op://vault/item/username":
                return CompletedProcess(0, "op-user\n")
            if field_ref == "op://vault/item/password":
                return CompletedProcess(0, "op-password\n")
            if field_ref == "op://vault/item/host":
                return CompletedProcess(0, "localhost\n")
            if field_ref == "op://vault/item/port":
                return CompletedProcess(0, "5432\n")
            if field_ref == "op://vault/item/database":
                return CompletedProcess(0, "op-db\n")
            return CompletedProcess(5, "", "item not found")
        if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert _db_config(Settings()) == ("op-user", "op-password", "localhost", 5432, "op-db")


def test_falls_back_to_home_env_when_1psa_cannot_resolve_db_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    #R010: ~/.env is the single fallback when 1psa cannot provide complete DB config.
    #R010-T01: Python test lane exists for ~/.env fallback requirement.
    _clear_secret_env(monkeypatch)
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    (fake_home / ".env").write_text(
        "username=env-user\npassword=env-password\nhost=localhost\nport=5434\ndatabase=env-db\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    #R010: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            return CompletedProcess(5, "", "not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert _db_config(Settings()) == ("env-user", "env-password", "localhost", 5434, "env-db")


def test_fails_clearly_when_1psa_and_home_env_both_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    #R010: Settings raises a clear runtime error when both resolution sources fail.
    #R010-T02: Python test lane exists for full resolution failure requirement.
    _clear_secret_env(monkeypatch)
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    (fake_home / ".env").write_text("username=incomplete\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    #R010: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            return CompletedProcess(5, "", "not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="Unable to resolve Teller DB config"):
        Settings()


def test_fails_clearly_when_resolved_db_port_is_not_an_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    #R010: Invalid DB port values are rejected even when other fields are present.
    #R010-T03: Python test lane exists for invalid port validation requirement.
    _clear_secret_env(monkeypatch)

    #R010: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            field_ref = _requested_secret_ref(command)
            if field_ref == "localhost_postgres_teller/username":
                return CompletedProcess(0, "teller\n")
            if field_ref == "localhost_postgres_teller/password":
                return CompletedProcess(0, "pw\n")
            if field_ref == "localhost_postgres_teller/host":
                return CompletedProcess(0, "localhost\n")
            if field_ref == "localhost_postgres_teller/port":
                return CompletedProcess(0, "not-a-port\n")
            if field_ref == "localhost_postgres_teller/database":
                return CompletedProcess(0, "teller\n")
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="port is not a valid integer"):
        Settings()


#R001: Test helper supports this requirement-focused scenario.
def _teller_db_credential(settings: Settings) -> str:
    return _settings_attr(settings, "teller_db_", "pass", "word")


#R015: Test helper supports this requirement-focused scenario.
def _anthropic_credential(settings: Settings) -> str:
    return _settings_attr(settings, "anthropic_", "api_", "key")


#R015: Test helper supports this requirement-focused scenario.
def _openai_credential(settings: Settings) -> str:
    return _settings_attr(settings, "openai_", "api_", "key")


def test_loads_anthropic_api_key_from_1psa_item_when_env_var_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: Anthropic key resolves from default 1psa item when ANTHROPIC_API_KEY env var is unset.
    #R015-T01: Python test lane exists for Anthropic 1psa resolution requirement.
    _clear_secret_env(monkeypatch)

    #R015: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            field_ref = _requested_secret_ref(command)
            if field_ref == "localhost_postgres_teller/username":
                return CompletedProcess(0, "teller\n")
            if field_ref == "localhost_postgres_teller/password":
                return CompletedProcess(0, "fixture-teller\n")
            if field_ref == "localhost_postgres_teller/host":
                return CompletedProcess(0, "localhost\n")
            if field_ref == "localhost_postgres_teller/port":
                return CompletedProcess(0, "5432\n")
            if field_ref == "localhost_postgres_teller/database":
                return CompletedProcess(0, "teller\n")
            if field_ref == "anthropic_api_key":
                return CompletedProcess(0, "fixture-claude\n")
            if field_ref == "openai_api_key":
                return CompletedProcess(0, "fixture-gpt\n")
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert _anthropic_credential(Settings()) == "fixture-claude"


def test_loads_openai_api_key_fallback_from_1psa_item_when_env_var_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: OpenAI fallback key resolves from default 1psa item when OPENAI_API_KEY env var is unset.
    #R015-T02: Python test lane exists for OpenAI 1psa resolution requirement.
    _clear_secret_env(monkeypatch)

    #R015: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            field_ref = _requested_secret_ref(command)
            if field_ref == "localhost_postgres_teller/username":
                return CompletedProcess(0, "teller\n")
            if field_ref == "localhost_postgres_teller/password":
                return CompletedProcess(0, "fixture-teller\n")
            if field_ref == "localhost_postgres_teller/host":
                return CompletedProcess(0, "localhost\n")
            if field_ref == "localhost_postgres_teller/port":
                return CompletedProcess(0, "5432\n")
            if field_ref == "localhost_postgres_teller/database":
                return CompletedProcess(0, "teller\n")
            if field_ref == "anthropic_api_key":
                return CompletedProcess(0, "fixture-claude\n")
            if field_ref == "openai_api_key":
                return CompletedProcess(0, "fixture-gpt\n")
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert _openai_credential(Settings()) == "fixture-gpt"


def test_env_var_override_beats_1psa_for_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: ANTHROPIC_API_KEY env var overrides any 1psa-resolved anthropic key value.
    #R015-T03: Python test lane exists for env override requirement.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-claude")

    #R015: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            field_ref = _requested_secret_ref(command)
            if field_ref == "localhost_postgres_teller/username":
                return CompletedProcess(0, "teller\n")
            if field_ref == "localhost_postgres_teller/password":
                return CompletedProcess(0, "fixture-teller\n")
            if field_ref == "localhost_postgres_teller/host":
                return CompletedProcess(0, "localhost\n")
            if field_ref == "localhost_postgres_teller/port":
                return CompletedProcess(0, "5432\n")
            if field_ref == "localhost_postgres_teller/database":
                return CompletedProcess(0, "teller\n")
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    assert _anthropic_credential(SettingsCls()) == "env-claude"


def test_tolerates_missing_ai_keys_in_1psa_and_keeps_settings_constructible(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: Missing AI items in 1psa resolve to empty strings without failing Settings construction.
    #R015-T04: Python test lane exists for missing AI keys requirement.
    _clear_secret_env(monkeypatch)

    #R015: Test helper supports this requirement-focused scenario.
    def handler(command, **kwargs):
        if command[0:2] in (["1psa", "-p"], ["1psa", "-f"], ["1psa", "read"]):
            field_ref = _requested_secret_ref(command)
            if field_ref == "localhost_postgres_teller/username":
                return CompletedProcess(0, "teller\n")
            if field_ref == "localhost_postgres_teller/password":
                return CompletedProcess(0, "fixture-teller\n")
            if field_ref == "localhost_postgres_teller/host":
                return CompletedProcess(0, "localhost\n")
            if field_ref == "localhost_postgres_teller/port":
                return CompletedProcess(0, "5432\n")
            if field_ref == "localhost_postgres_teller/database":
                return CompletedProcess(0, "teller\n")
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert _anthropic_credential(Settings()) == ""


def test_mailcart_body_enrichment_flags_default_to_enabled_and_limit_75(monkeypatch: pytest.MonkeyPatch) -> None:
    #R030: Default Mailcart body-enrichment feature flag is enabled with a sane default limit.
    #R030-T01: Python test lane exists for enrichment default requirement.
    _clear_secret_env(monkeypatch)
    monkeypatch.delenv("MATCHY_MAILCART_BODY_ENRICHMENT", raising=False)
    monkeypatch.delenv("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT", raising=False)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    settings = SettingsCls()
    assert settings.mailcart_body_enrichment_enabled is True
    assert settings.mailcart_body_enrichment_limit == 75


def test_default_anthropic_model_is_the_dated_stable_id_and_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    #R035: Anthropic model defaults to a pinned dated id; env var overrides it.
    #R035-T01: Python test lane exists for default anthropic model requirement.
    #R035-T02: Python test lane exists for anthropic model override requirement.
    _clear_secret_env(monkeypatch)
    monkeypatch.delenv("MATCHY_ANTHROPIC_MODEL", raising=False)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    assert SettingsCls().anthropic_model == "claude-sonnet-4-5"
    monkeypatch.setenv("MATCHY_ANTHROPIC_MODEL", "claude-opus-x")
    SettingsCls = _reload_settings_class(monkeypatch)
    assert SettingsCls().anthropic_model == "claude-opus-x"


def test_mailcart_body_enrichment_flags_honor_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    #R030: Mailcart body-enrichment env overrides flip the flag and resize the limit.
    #R030-T02: Python test lane exists for enrichment override requirement.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("MATCHY_MAILCART_BODY_ENRICHMENT", "false")
    monkeypatch.setenv("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT", "10")
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    settings = SettingsCls()
    assert settings.mailcart_body_enrichment_enabled is False
    assert settings.mailcart_body_enrichment_limit == 10


def test_mailcart_search_timeout_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    #R040-T01: Default mailcart_search_timeout_seconds is 45 when unset.
    #R040-T02: MATCHY_MAILCART_SEARCH_TIMEOUT_SECONDS overrides the default.
    _clear_secret_env(monkeypatch)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    settings = SettingsCls()
    assert settings.mailcart_search_timeout_seconds == 45
    monkeypatch.setenv("MATCHY_MAILCART_SEARCH_TIMEOUT_SECONDS", "30")
    SettingsCls2 = _reload_settings_class(monkeypatch)
    settings2 = SettingsCls2()
    assert settings2.mailcart_search_timeout_seconds == 30


def test_near_duplicate_hamming_distance_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    #R055-T05: near_duplicate_max_hamming_distance defaults to 0 and is configurable via env var.
    _clear_secret_env(monkeypatch)
    monkeypatch.delenv("MATCHY_NEAR_DUPLICATE_MAX_HAMMING_DISTANCE", raising=False)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    settings = SettingsCls()
    assert settings.near_duplicate_max_hamming_distance == 0
    monkeypatch.setenv("MATCHY_NEAR_DUPLICATE_MAX_HAMMING_DISTANCE", "7")
    SettingsCls2 = _reload_settings_class(monkeypatch)
    settings2 = SettingsCls2()
    assert settings2.near_duplicate_max_hamming_distance == 7


def test_mailcart_ca_bundle_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    #R045-T01: Default mailcart_ca_bundle is empty (auto-resolve) when unset.
    #R045-T02: MATCHY_MAILCART_CA_BUNDLE exposes the explicit path.
    _clear_secret_env(monkeypatch)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    settings = SettingsCls()
    assert settings.mailcart_ca_bundle == ""
    monkeypatch.setenv("MATCHY_MAILCART_CA_BUNDLE", "/custom/ca.pem")
    SettingsCls2 = _reload_settings_class(monkeypatch)
    settings2 = SettingsCls2()
    assert settings2.mailcart_ca_bundle == "/custom/ca.pem"


def test_cldr_currencies_cache_settings_default_and_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    #R050: CLDR currencies cache path, refresh flag, and timeout expose env-configurable startup behavior.
    #R050-T01: Python test lane exists for CLDR currencies cache setting defaults and overrides.
    _clear_secret_env(monkeypatch)
    monkeypatch.delenv("MATCHY_CLDR_CURRENCIES_CACHE_PATH", raising=False)
    monkeypatch.delenv("MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED", raising=False)
    monkeypatch.delenv("MATCHY_CLDR_CURRENCIES_REFRESH_TIMEOUT_SECONDS", raising=False)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    settings = SettingsCls()
    assert settings.cldr_currencies_cache_path.endswith(".cache/matchy/cldr-currencies-en.json")
    assert settings.cldr_currencies_refresh_enabled is True
    assert settings.cldr_currencies_refresh_timeout_seconds == 5
    override_path = tmp_path / "currencies.json"
    monkeypatch.setenv("MATCHY_CLDR_CURRENCIES_CACHE_PATH", str(override_path))
    monkeypatch.setenv("MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED", "false")
    monkeypatch.setenv("MATCHY_CLDR_CURRENCIES_REFRESH_TIMEOUT_SECONDS", "9")
    settings2 = SettingsCls()
    assert settings2.cldr_currencies_cache_path == str(override_path)
    assert settings2.cldr_currencies_refresh_enabled is False
    assert settings2.cldr_currencies_refresh_timeout_seconds == 9
