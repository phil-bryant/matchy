import pytest


@pytest.fixture(autouse=True)
def _stub_settings_secrets(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.fspath and request.node.fspath.basename == "test_settings.py":
        return
    monkeypatch.setenv("TELLER_DB_PASSWORD", "pw")
    monkeypatch.setattr("matchy.settings.Settings._resolve_teller_db_password", lambda self: "pw")
    monkeypatch.setattr(
        "matchy.settings.Settings._resolve_optional_api_key",
        lambda self, env_value, item_name: env_value.strip(),
    )
