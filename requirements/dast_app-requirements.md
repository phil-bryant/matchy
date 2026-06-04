# DAST app entrypoint Requirements

## Scope

Applies to `dast_app.py`.

R001  Statement: The module is importable without side effects and only serves when run directly.
Design: Guard the `uvicorn.run` call behind `if __name__ == "__main__"` so unit tests can import helpers.
Tests:
- R001-T01: Importing `dast_app` does not start a server.

R005  Statement: Settings resolve from the first non-empty candidate environment variable, else a default.
Design: `_resolve(names, default)` scans candidates in order and returns the first non-empty value.
Tests:
- R005-T01: The first non-empty candidate wins over later candidates.
- R005-T02: The default is returned when no candidate is set.

R010  Statement: The entrypoint binds host, port, and TLS material from the dynamic-lane environment contract.
Design: Read host/port from MATCHY_/CLASSIFICATION_/CLASSY_/TELLER_CLASSIFIER_ API variables and TLS cert/key
from the matchy or teller classifier TLS variables, defaulting to the local classifier certificate pair.
Tests:
- R010-T01: TLS cert/key resolution prefers explicit matchy overrides over the default certificate pair.
