from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import dast_app


def test_dast_app_imports_without_starting_server() -> None:
    #R001-T01: Importing the module must not start a server (uvicorn.run is guarded by __main__).
    module = importlib.import_module("dast_app")
    assert hasattr(module, "main")
    assert callable(module._resolve)


def test_resolve_prefers_first_non_empty_candidate(monkeypatch) -> None:
    #R005-T01: The first non-empty candidate environment variable wins over later candidates.
    monkeypatch.delenv("FIRST", raising=False)
    monkeypatch.setenv("SECOND", "second-value")
    monkeypatch.setenv("THIRD", "third-value")
    assert dast_app._resolve(["FIRST", "SECOND", "THIRD"], "fallback") == "second-value"


def test_resolve_returns_default_when_unset(monkeypatch) -> None:
    #R005-T02: The default is returned when no candidate environment variable is set.
    for name in ("A_UNSET", "B_UNSET"):
        monkeypatch.delenv(name, raising=False)
    assert dast_app._resolve(["A_UNSET", "B_UNSET"], "fallback") == "fallback"


def test_resolve_tls_overrides_take_precedence(monkeypatch) -> None:
    #R010-T01: Explicit matchy TLS overrides take precedence over the default certificate pair.
    monkeypatch.setenv("MATCHY_API_TLS_CERT_FILE", "/custom/cert.pem")
    monkeypatch.delenv("TELLER_CLASSIFIER_TLS_CERT_FILE", raising=False)
    resolved = dast_app._resolve(["MATCHY_API_TLS_CERT_FILE", "TELLER_CLASSIFIER_TLS_CERT_FILE"], "/default/cert.pem")
    assert resolved == "/custom/cert.pem"


def test_resolve_mkcert_root_ca_uses_home_library_path_when_present(monkeypatch, tmp_path) -> None:
    #R400-T01: mkcert root CA resolution prefers the standard home-library location when the file exists.
    home_root = tmp_path / "Library" / "Application Support" / "mkcert"
    home_root.mkdir(parents=True)
    root_ca = home_root / "rootCA.pem"
    root_ca.write_text("pem", encoding="utf-8")
    monkeypatch.setattr(dast_app.Path, "home", lambda: tmp_path)
    assert dast_app._resolve_mkcert_root_ca() == str(root_ca)


def test_resolve_mkcert_root_ca_returns_empty_when_no_location_is_available(monkeypatch, tmp_path) -> None:
    #R400-T02: mkcert root CA resolution returns an empty value when neither home path nor mkcert command resolves a file.
    monkeypatch.setattr(dast_app.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(dast_app.subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=1, stdout=""))
    assert dast_app._resolve_mkcert_root_ca() == ""
