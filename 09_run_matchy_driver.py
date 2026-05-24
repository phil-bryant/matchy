#!/usr/bin/env python3
#R001: Provide executable entrypoint that drives pending transaction match runs.
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import os
import time
from time import perf_counter
from urllib.parse import urlparse

import requests

DEFAULT_API_BASE_URL = "http://127.0.0.1:8790"
DEFAULT_LIMIT = 10
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_TRIGGER_SOURCE = "auto"
_ALLOWED_API_HOSTS = frozenset({"127.0.0.1", "localhost"})


def _startup_log(start_time_seconds: float, phase: str, details: str = "", profile_enabled: bool = False) -> None:
    if profile_enabled:
        elapsed_seconds = perf_counter() - start_time_seconds
        suffix = f" | {details}" if details else ""
        print(f"[matchy-driver-startup +{elapsed_seconds:7.3f}s] {phase}{suffix}", flush=True)


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


def _post_pending_run_with_profile_heartbeat(
    api_base_url: str,
    limit: int,
    lookback_days: int,
    trigger_source: str,
    timeout_seconds: int,
    startup_started_at: float,
    run_counter: int,
    profile_enabled: bool,
) -> dict:
    response_payload: dict = {"results": []}
    heartbeat_seconds = 5
    elapsed_wait_seconds = 0
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_post_pending_run, api_base_url, limit, lookback_days, trigger_source, timeout_seconds)
        finished = False
        while not finished:
            try:
                response_payload = future.result(timeout=heartbeat_seconds)
                finished = True
            except TimeoutError:
                elapsed_wait_seconds += heartbeat_seconds
                _startup_log(
                    startup_started_at,
                    "run-waiting",
                    f"run={run_counter} elapsed_wait_seconds={elapsed_wait_seconds} timeout_seconds={timeout_seconds}",
                    profile_enabled=profile_enabled,
                )
    return response_payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Matchy pending-transaction driver")
    parser.add_argument("--profile", action="store_true", default=False)
    parser.add_argument("--api-base-url", default=os.environ.get("MATCHY_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--limit", type=int, default=_env_int("MATCHY_DRIVER_LIMIT", DEFAULT_LIMIT, 1))
    parser.add_argument("--lookback-days", type=int, default=_env_int("MATCHY_DRIVER_LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS, 1))
    parser.add_argument("--interval-seconds", type=int, default=_env_int("MATCHY_DRIVER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS, 1))
    parser.add_argument("--timeout-seconds", type=int, default=_env_int("MATCHY_DRIVER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, 1))
    parser.add_argument("--max-runs", type=int, default=_env_int("MATCHY_DRIVER_MAX_RUNS", 0, 0))
    parser.add_argument("--trigger-source", default=os.environ.get("MATCHY_DRIVER_TRIGGER_SOURCE", DEFAULT_TRIGGER_SOURCE).strip() or DEFAULT_TRIGGER_SOURCE)
    parser.add_argument("--once", action="store_true", default=_env_bool("MATCHY_DRIVER_ONCE", False))
    return parser.parse_args()


def _count_selected_messages(results: list[dict]) -> int:
    total = 0
    for row in results:
        selected_ids = row.get("selected_message_ids", [])
        if isinstance(selected_ids, list):
            total += len(selected_ids)
    return total


#R005: Loop on an interval and call pending-run endpoint with deterministic defaults or env overrides.
def _run_driver_loop() -> int:
    startup_started_at = perf_counter()
    args = _parse_args()
    _startup_log(startup_started_at, "args-parsed", profile_enabled=args.profile)
    api_base_url = _validated_api_base_url(args.api_base_url)
    _startup_log(startup_started_at, "api-base-url-validated", f"api_base_url={api_base_url}", profile_enabled=args.profile)
    limit = args.limit
    lookback_days = args.lookback_days
    interval_seconds = args.interval_seconds
    timeout_seconds = args.timeout_seconds
    max_runs = args.max_runs
    trigger_source = args.trigger_source
    run_once = args.once
    _startup_log(
        startup_started_at,
        "driver-configured",
        f"once={str(run_once).lower()} max_runs={max_runs} interval_seconds={interval_seconds}",
        profile_enabled=args.profile,
    )
    run_counter = 0
    keep_running = True
    while keep_running:
        run_counter += 1
        run_started_at = perf_counter()
        status_text = "ok"
        results: list[dict] = []
        failure_text = ""
        _startup_log(
            startup_started_at,
            "run-start",
            f"run={run_counter} timeout_seconds={timeout_seconds} limit={limit} lookback_days={lookback_days}",
            profile_enabled=args.profile,
        )
        try:
            payload = _post_pending_run_with_profile_heartbeat(
                api_base_url=api_base_url,
                limit=limit,
                lookback_days=lookback_days,
                trigger_source=trigger_source,
                timeout_seconds=timeout_seconds,
                startup_started_at=startup_started_at,
                run_counter=run_counter,
                profile_enabled=args.profile,
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
        _startup_log(
            startup_started_at,
            "run-complete",
            f"run={run_counter} status={status_text} phase_elapsed={perf_counter() - run_started_at:7.3f}s",
            profile_enabled=args.profile,
        )
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
            _startup_log(
                startup_started_at,
                "sleeping-before-next-run",
                f"run={run_counter} interval_seconds={interval_seconds}",
                profile_enabled=args.profile,
            )
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
