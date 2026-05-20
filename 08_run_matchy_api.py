#!/usr/bin/env python3
#R001: Provide executable entrypoint for Matchy API.
import os
import socket

import requests
from matchy.api import create_app
import uvicorn

MATCHY_HEALTH_URL = "http://127.0.0.1:8790/health"


def _is_port_in_use(host: str, port: int) -> bool:
    in_use = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.25)
    result = sock.connect_ex((host, port))
    if result == 0:
        in_use = True
    sock.close()
    return in_use


def _is_matchy_healthy() -> bool:
    healthy = False
    try:
        response = requests.get(MATCHY_HEALTH_URL, timeout=1.5)
        if response.status_code == 200 and '"status":"ok"' in response.text:
            healthy = True
    except requests.RequestException:
        healthy = False
    return healthy


if __name__ == "__main__":
    guard_enabled = os.environ.get("MATCHY_PORT_GUARD", "true").lower() == "true"
    if guard_enabled and _is_port_in_use("127.0.0.1", 8790):
        if _is_matchy_healthy():
            print("Matchy API already running on 127.0.0.1:8790; reusing existing process.")
            raise SystemExit(0)
        raise SystemExit("Port 8790 is already in use by another process.")
    #R005: Launch local API server on deterministic host/port.
    uvicorn.run(create_app(), host="127.0.0.1", port=8790)
