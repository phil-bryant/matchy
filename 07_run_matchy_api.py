#!/usr/bin/env python3
#R001: Provide executable entrypoint for Matchy API.
from matchy.api import create_app
import uvicorn


if __name__ == "__main__":
    #R005: Launch local API server on deterministic host/port.
    uvicorn.run(create_app(), host="127.0.0.1", port=8790)
