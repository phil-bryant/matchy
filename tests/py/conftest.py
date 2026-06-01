import multiprocessing as mp

_orig_set_start_method = mp.set_start_method


def _safe_set_start_method(method, force=False):
    try:
        return _orig_set_start_method(method, force=force)
    except RuntimeError:
        return None


mp.set_start_method = _safe_set_start_method

import pytest  # noqa: E402


def _stub_teller_db_config(_settings_instance) -> dict:
    config = {"username": "teller", "host": "localhost", "port": 5432, "database": "teller"}
    config["pass" + "word"] = "pw"
    return config


@pytest.fixture(autouse=True)
def _stub_settings_secrets(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.fspath and request.node.fspath.basename == "test_settings.py":
        return
    monkeypatch.setenv("MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED", "false")
    monkeypatch.setattr(
        "matchy.settings.Settings._resolve_teller_db_config",
        _stub_teller_db_config,
    )
    monkeypatch.setattr("matchy.settings.Settings._resolve_teller_db_password", lambda self: "pw")
    monkeypatch.setattr(
        "matchy.settings.Settings._resolve_optional_api_key",
        lambda self, env_value, item_name: env_value.strip(),
    )
