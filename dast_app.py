#!/usr/bin/env python3
"""DAST entrypoint: serve the matchy FastAPI app over TLS so the dynamic security lane can scan it."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import uvicorn


#R005: Resolve a setting from the first non-empty candidate environment variable, else a default.
def _resolve(names: list[str], default: str) -> str:
    resolved = default
    found = False
    for name in names:
        value = os.environ.get(name, "")
        if value and not found:
            resolved = value
            found = True
    return resolved


# Resolve mkcert root CA for Mailcart TLS verification when DAST runs against localhost HTTPS stubs.
def _resolve_mkcert_root_ca() -> str:
    resolved = ""
    home_root = Path.home() / "Library" / "Application Support" / "mkcert" / "rootCA.pem"
    if home_root.is_file():
        resolved = str(home_root)
    if not resolved:
        try:
            completed = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True, timeout=5)
            if completed.returncode == 0:
                mkcert_root = Path(completed.stdout.strip()) / "rootCA.pem"
                if mkcert_root.is_file():
                    resolved = str(mkcert_root)
        except (OSError, subprocess.SubprocessError):
            resolved = ""
    return resolved


#R010: Bind host/port/TLS from the dynamic-lane environment contract and serve the matchy app over HTTPS.
def main() -> None:
    home_certs = Path.home() / ".teller"
    host = _resolve(["MATCHY_API_HOST", "CLASSIFICATION_API_HOST", "CLASSY_API_HOST",
                     "TELLER_CLASSIFIER_API_HOST"], "127.0.0.1")
    port = int(_resolve(["MATCHY_API_PORT", "CLASSIFICATION_API_PORT", "CLASSY_API_PORT",
                         "TELLER_CLASSIFIER_API_PORT"], "8787"))
    cert = _resolve(["MATCHY_API_TLS_CERT_FILE", "TELLER_CLASSIFIER_TLS_CERT_FILE"],
                    str(home_certs / "classifier-localhost-cert.pem"))
    key = _resolve(["MATCHY_API_TLS_KEY_FILE", "TELLER_CLASSIFIER_TLS_KEY_FILE"],
                   str(home_certs / "classifier-localhost-key.pem"))
    configured_mailcart_ca = os.environ.get("MATCHY_MAILCART_CA_BUNDLE", "").strip()
    if not configured_mailcart_ca:
        mkcert_root_ca = _resolve_mkcert_root_ca()
        if mkcert_root_ca:
            os.environ["MATCHY_MAILCART_CA_BUNDLE"] = mkcert_root_ca
    configured_api_auth = os.environ.get("MATCHY_API_AUTH_TOKEN", "").strip()
    if not configured_api_auth:
        fallback_api_auth = _resolve(["TELLER_CLASSIFIER_WRITE_TOKEN", "DAST_WRITE_TOKEN"], "")
        if fallback_api_auth:
            os.environ["MATCHY_API_AUTH_TOKEN"] = fallback_api_auth
    from matchy.api import create_app
    uvicorn.run(create_app(), host=host, port=port, ssl_certfile=cert, ssl_keyfile=key, log_level="warning")


#R001: Run only when invoked directly so the module stays importable for unit tests.
if __name__ == "__main__":
    main()
