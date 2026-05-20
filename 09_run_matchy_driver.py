#!/usr/bin/env python3
#R001: Provide executable entrypoint that drives pending transaction match runs.
import os
import time
from urllib.parse import urlparse

import requests

DEFAULT_API_BASE_URL = "http://127.0.0.1:8790"
DEFAULT_LIMIT = 100
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_TRIGGER_SOURCE = "auto"
_ALLOWED_API_HOSTS = frozenset({"127.0.0.1", "localhost"})


def _env_int(name: str, default_value: int, min_value: int) -> int:
    value = default_value
    raw = os.environ.get(name, str(default_value)).strip()
    try:
        parsed = int(raw)
        if parsed >= min_value:
            value = parsed
    except ValueError:
        value = default_value
    return value


def _env_bool(name: str, default_value: bool) -> bool:
    value = default_value
    raw = os.environ.get(name, "true" if default_value else "false").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        value = True
    if raw in {"0", "false", "no", "off"}:
        value = False
    return value


def _validated_api_base_url(raw: str) -> str:
    candidate = raw.strip() or DEFAULT_API_BASE_URL
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"MATCHY_API_BASE_URL must use http or https, got scheme {parsed.scheme!r}")
    hostname = parsed.hostname
    if hostname not in _ALLOWED_API_HOSTS:
        raise ValueError(f"MATCHY_API_BASE_URL host must be loopback (127.0.0.1 or localhost), got {hostname!r}")
    return candidate.rstrip("/")


def _post_pending_run(api_base_url: str, limit: int, lookback_days: int, trigger_source: str, timeout_seconds: int) -> dict:
    payload = {"limit": limit, "lookback_days": lookback_days, "trigger_source": trigger_source}
    response_payload: dict = {"results": []}
    response = requests.post(
        f"{api_base_url}/v1/matchy/runs/pending",
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    parsed = response.json()
    if isinstance(parsed, dict):
        response_payload = parsed
    return response_payload


def _count_selected_messages(results: list[dict]) -> int:
    total = 0
    for row in results:
        selected_ids = row.get("selected_message_ids", [])
        if isinstance(selected_ids, list):
            total += len(selected_ids)
    return total


#R005: Loop on an interval and call pending-run endpoint with deterministic defaults or env overrides.
def _run_driver_loop() -> int:
    api_base_url = _validated_api_base_url(os.environ.get("MATCHY_API_BASE_URL", DEFAULT_API_BASE_URL))
    limit = _env_int("MATCHY_DRIVER_LIMIT", DEFAULT_LIMIT, 1)
    lookback_days = _env_int("MATCHY_DRIVER_LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS, 1)
    interval_seconds = _env_int("MATCHY_DRIVER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS, 1)
    timeout_seconds = _env_int("MATCHY_DRIVER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, 1)
    max_runs = _env_int("MATCHY_DRIVER_MAX_RUNS", 0, 0)
    trigger_source = os.environ.get("MATCHY_DRIVER_TRIGGER_SOURCE", DEFAULT_TRIGGER_SOURCE).strip() or DEFAULT_TRIGGER_SOURCE
    run_once = _env_bool("MATCHY_DRIVER_ONCE", False)
    run_counter = 0
    keep_running = True
    while keep_running:
        run_counter += 1
        status_text = "ok"
        results: list[dict] = []
        failure_text = ""
        try:
            payload = _post_pending_run(
                api_base_url=api_base_url,
                limit=limit,
                lookback_days=lookback_days,
                trigger_source=trigger_source,
                timeout_seconds=timeout_seconds,
            )
            rows = payload.get("results", [])
            if isinstance(rows, list):
                results = rows
        except requests.HTTPError as exc:
            status_text = "http_error"
            failure_text = str(exc.response.status_code) if exc.response is not None else str(exc)
        except requests.RequestException as exc:
            status_text = "url_error"
            failure_text = str(exc)
        except Exception as exc:
            status_text = "error"
            failure_text = str(exc)
        selected_count = _count_selected_messages(results)
        print(
            f"driver_run={run_counter} status={status_text} batch_size={len(results)} selected_messages={selected_count} "
            f"trigger_source={trigger_source} failure={failure_text}"
        )
        done_for_once = run_once
        done_for_max_runs = max_runs > 0 and run_counter >= max_runs
        if done_for_once or done_for_max_runs:
            keep_running = False
        if keep_running:
            time.sleep(interval_seconds)
    return 0


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = _run_driver_loop()
    except KeyboardInterrupt:
        print("Matchy driver interrupted; exiting.")
        exit_code = 0
    raise SystemExit(exit_code)
