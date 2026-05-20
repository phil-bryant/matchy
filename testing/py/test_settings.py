#R001: Python test lane coverage for default 1psa teller password resolution.
#R005: Python test lane coverage for 1psa reference overrides.
#R010: Python test lane coverage for 1psa failure handling.
#R015: Python test lane coverage for AI key resolution.
#R030: Python test lane coverage for mailcart body enrichment defaults.
#R035: Python test lane coverage for anthropic model defaults.
#R001-T01: Python test lane exists for default teller password requirement.
#R005-T01: Python test lane exists for item-name override requirement.
#R005-T02: Python test lane exists for op:// reference requirement.
#R010-T01: Python test lane exists for 1psa lookup failure requirement.
#R010-T02: Python test lane exists for OP auth failure requirement.
#R015-T01: Python test lane exists for Anthropic 1psa resolution requirement.
#R015-T02: Python test lane exists for OpenAI 1psa resolution requirement.
#R015-T03: Python test lane exists for env override requirement.
#R015-T04: Python test lane exists for missing AI keys requirement.
#R030-T01: Python test lane exists for enrichment default requirement.
#R030-T02: Python test lane exists for enrichment override requirement.
#R035-T01: Python test lane exists for default anthropic model requirement.
#R035-T02: Python test lane exists for anthropic model override requirement.

from __future__ import annotations

import importlib
import subprocess
from typing import Any

import pytest

import matchy.settings as settings_module
from matchy.settings import Settings


class CompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _install_run_stub(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    def fake_run(command, **kwargs: Any):
        return handler(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)


def _clear_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELLER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("TELLER_DB_PASSWORD_1PSA_REF", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _optional_miss_handler(command, **kwargs):
    if command == ["1psa", "-p", "localhost_postgres_teller"]:
        return CompletedProcess(0, "secret-default\n")
    if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
        return CompletedProcess(5, "", "item not found")
    raise AssertionError(f"unexpected command: {command}")


def _reload_settings_class(monkeypatch: pytest.MonkeyPatch):
    importlib.reload(settings_module)
    return settings_module.Settings


def test_loads_teller_password_from_default_1psa_item_when_no_refs_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    #R001: Default 1psa item resolves teller password without password env vars.
    _clear_secret_env(monkeypatch)
    _install_run_stub(monkeypatch, _optional_miss_handler)
    assert Settings().teller_db_password == "secret-default"


def test_loads_teller_password_through_1psa_item_reference_override(monkeypatch: pytest.MonkeyPatch) -> None:
    #R005: Item-name override is resolved through 1psa -p.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("TELLER_DB_PASSWORD_1PSA_REF", "custom_item")

    def handler(command, **kwargs):
        if command == ["1psa", "-p", "custom_item"]:
            return CompletedProcess(0, "secret-from-1psa\n")
        if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert Settings().teller_db_password == "secret-from-1psa"


def test_loads_teller_password_through_1psa_read_for_op_references(monkeypatch: pytest.MonkeyPatch) -> None:
    #R005: op:// references are resolved through 1psa read.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token-ok")
    monkeypatch.setenv("TELLER_DB_PASSWORD_1PSA_REF", "op://vault/item/password")

    def handler(command, **kwargs):
        if command == ["1psa", "read", "op://vault/item/password"]:
            return CompletedProcess(0, "secret-op-ref\n")
        if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert Settings().teller_db_password == "secret-op-ref"


def test_fails_clearly_when_1psa_lookup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    #R010: 1psa lookup failures produce explicit runtime errors.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token-ok")
    monkeypatch.setenv("TELLER_DB_PASSWORD_1PSA_REF", "op://vault/item/password")

    def handler(command, **kwargs):
        if command == ["1psa", "read", "op://vault/item/password"]:
            raise subprocess.CalledProcessError(9, command, stderr="boom")
        if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="1psa failed to resolve TELLER_DB_PASSWORD_1PSA_REF"):
        Settings()


def test_fails_clearly_when_op_token_is_invalid_for_1psa_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    #R010: Invalid OP service-account token returns targeted auth guidance.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token-bad")
    monkeypatch.setenv("TELLER_DB_PASSWORD_1PSA_REF", "localhost_postgres_teller")

    def handler(command, **kwargs):
        if command == ["1psa", "-p", "localhost_postgres_teller"]:
            raise subprocess.CalledProcessError(
                1,
                command,
                stderr='Failed to create client: Post "https://my.1password.com/api/v3/auth/start?": Forbidden',
            )
        if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="1psa authentication failed for OP_SERVICE_ACCOUNT_TOKEN"):
        Settings()


def test_loads_anthropic_api_key_from_1psa_item_when_env_var_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: Anthropic key resolves from default 1psa item when ANTHROPIC_API_KEY env var is unset.
    _clear_secret_env(monkeypatch)

    def handler(command, **kwargs):
        if command == ["1psa", "-p", "localhost_postgres_teller"]:
            return CompletedProcess(0, "secret-teller\n")
        if command == ["1psa", "-p", "anthropic_api_key"]:
            return CompletedProcess(0, "secret-claude\n")
        if command == ["1psa", "-p", "openai_api_key"]:
            return CompletedProcess(0, "secret-gpt\n")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert Settings().anthropic_api_key == "secret-claude"


def test_loads_openai_api_key_fallback_from_1psa_item_when_env_var_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: OpenAI fallback key resolves from default 1psa item when OPENAI_API_KEY env var is unset.
    _clear_secret_env(monkeypatch)

    def handler(command, **kwargs):
        if command == ["1psa", "-p", "localhost_postgres_teller"]:
            return CompletedProcess(0, "secret-teller\n")
        if command == ["1psa", "-p", "anthropic_api_key"]:
            return CompletedProcess(0, "secret-claude\n")
        if command == ["1psa", "-p", "openai_api_key"]:
            return CompletedProcess(0, "secret-gpt\n")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    assert Settings().openai_api_key == "secret-gpt"


def test_env_var_override_beats_1psa_for_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: ANTHROPIC_API_KEY env var overrides any 1psa-resolved anthropic key value.
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-claude")

    def handler(command, **kwargs):
        if command == ["1psa", "-p", "localhost_postgres_teller"]:
            return CompletedProcess(0, "secret-teller\n")
        if command[0:2] in (["1psa", "-p"], ["1psa", "read"]):
            return CompletedProcess(5, "", "item not found")
        raise AssertionError(f"unexpected command: {command}")

    _install_run_stub(monkeypatch, handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    assert SettingsCls().anthropic_api_key == "env-claude"


def test_tolerates_missing_ai_keys_in_1psa_and_keeps_settings_constructible(monkeypatch: pytest.MonkeyPatch) -> None:
    #R015: Missing AI items in 1psa resolve to empty strings without failing Settings construction.
    _clear_secret_env(monkeypatch)

    def handler(command, **kwargs):
        if command == ["1psa", "-p", "localhost_postgres_teller"]:
            return CompletedProcess(0, "secret-teller\n")
        return CompletedProcess(5, "", "item not found")

    _install_run_stub(monkeypatch, handler)
    assert Settings().anthropic_api_key == ""


def test_mailcart_body_enrichment_flags_default_to_enabled_and_limit_75(monkeypatch: pytest.MonkeyPatch) -> None:
    #R030: Default Mailcart body-enrichment feature flag is enabled with a sane default limit.
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
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("MATCHY_MAILCART_BODY_ENRICHMENT", "false")
    monkeypatch.setenv("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT", "10")
    _install_run_stub(monkeypatch, _optional_miss_handler)
    SettingsCls = _reload_settings_class(monkeypatch)
    settings = SettingsCls()
    assert settings.mailcart_body_enrichment_enabled is False
    assert settings.mailcart_body_enrichment_limit == 10
