import multiprocessing as mp

_orig_set_start_method = mp.set_start_method


#R001: Test bootstrap safely wraps multiprocessing start-method setup for repeated pytest imports.
def _safe_set_start_method(method, force=False):
    try:
        return _orig_set_start_method(method, force=force)
    except RuntimeError:
        return None


mp.set_start_method = _safe_set_start_method

import pytest  # noqa: E402


#R001: Test fixture helper supplies deterministic Teller DB settings for unit lanes.
def _stub_teller_db_config(_settings_instance) -> dict:
    config = {"username": "teller", "host": "localhost", "port": 5432, "database": "teller"}
    config["pass" + "word"] = "pw"
    return config


@pytest.fixture(autouse=True)
#R001: Autouse fixture applies stable secret/environment stubs for non-settings pytest modules.
def _stub_settings_secrets(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.fspath and request.node.fspath.basename == "test_settings.py":
        return
    monkeypatch.setenv("MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED", "false")
    monkeypatch.setenv("MATCHY_API_AUTH_TOKEN", "test-matchy-api-token")
    #R030: Pin the postgres SQL rendering for unit lanes so assertions stay
    #R030: deterministic regardless of the developer's active DB profile.
    monkeypatch.setattr("matchy.db_target._IS_SQLITE", False)
    monkeypatch.setattr("matchy.settings._teller_profile_target", lambda: "")
    monkeypatch.setattr(
        "matchy.settings.Settings._resolve_teller_db_config",
        _stub_teller_db_config,
    )
    monkeypatch.setattr("matchy.settings.Settings._resolve_teller_db_password", lambda self: "pw")
    monkeypatch.setattr(
        "matchy.settings.Settings._resolve_optional_api_key",
        lambda self, env_value, item_name: env_value.strip(),
    )
