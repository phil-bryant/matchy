#!/usr/bin/env python3
#R001: Provide executable entrypoint for Matchy API.
import argparse
import http.client
import os
import socket
import subprocess
from time import perf_counter

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
DEFAULT_API_AUTH_TOKEN = "matchy-local-dev-token"
DEFAULT_ENGINE = "cpp"
_CMAKE_BUILD_TYPE_ARG = "-DCMAKE_BUILD_TYPE=RelWithDebInfo"  # pragma: allowlist secret


#R005: Port guard checks deterministic host/port occupancy before startup.
def _is_port_in_use(host: str, port: int) -> bool:
    in_use = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.25)
    result = sock.connect_ex((host, port))
    if result == 0:
        in_use = True
    sock.close()
    return in_use


#R005: Health probe confirms reusable Matchy process on the guarded bind target.
def _is_matchy_healthy(host: str, port: int) -> bool:
    healthy = False
    connection: http.client.HTTPConnection | None = None
    try:
        connection = http.client.HTTPConnection(host=host, port=port, timeout=1.5)
        connection.request("GET", "/health")
        response = connection.getresponse()
        body_text = response.read().decode("utf-8", errors="replace")
        if response.status == 200 and '"status":"ok"' in body_text:
            healthy = True
    except (http.client.HTTPException, OSError):
        healthy = False
    finally:
        if connection is not None:
            connection.close()
    return healthy


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Matchy API")
    #R015: Engine selection (cpp default, python opt-in) is exposed for the C++ cutover with A/B testing.
    parser.add_argument("--engine", choices=["cpp", "python"], default=None)
    #R010: Startup profiling logs are opt-in via --profile.
    parser.add_argument("--host", default=os.environ.get("MATCHY_API_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MATCHY_API_PORT", str(DEFAULT_PORT)) or DEFAULT_PORT))
    parser.add_argument("--profile", action="store_true", default=False)
    parser.add_argument("--port-guard", dest="port_guard", action="store_true", default=None)
    parser.add_argument("--no-port-guard", dest="port_guard", action="store_false")
    parser.add_argument("--mailcart-body-enrichment", choices=["true", "false"], default=None)
    parser.add_argument("--mailcart-body-enrichment-limit", type=int, default=None)
    parser.add_argument("--mailcart-body-enrichment-timeout-seconds", type=int, default=None)
    parser.add_argument("--mailcart-body-enrichment-max-workers", type=int, default=None)
    parser.add_argument("--mailcart-get-message-timeout-seconds", type=int, default=None)
    parser.add_argument("--pending-max-workers", type=int, default=None)
    return parser.parse_args()


#R005: CLI overrides map to env vars consumed by Matchy runtime settings.
def _apply_argument_overrides(args: argparse.Namespace) -> None:
    if args.mailcart_body_enrichment is not None:
        os.environ["MATCHY_MAILCART_BODY_ENRICHMENT"] = args.mailcart_body_enrichment
    if args.mailcart_body_enrichment_limit is not None:
        os.environ["MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT"] = str(args.mailcart_body_enrichment_limit)
    if args.mailcart_body_enrichment_timeout_seconds is not None:
        os.environ["MATCHY_MAILCART_BODY_ENRICHMENT_TIMEOUT_SECONDS"] = str(args.mailcart_body_enrichment_timeout_seconds)
    if args.mailcart_body_enrichment_max_workers is not None:
        os.environ["MATCHY_MAILCART_BODY_ENRICHMENT_MAX_WORKERS"] = str(args.mailcart_body_enrichment_max_workers)
    if args.mailcart_get_message_timeout_seconds is not None:
        os.environ["MATCHY_MAILCART_GET_MESSAGE_TIMEOUT_SECONDS"] = str(args.mailcart_get_message_timeout_seconds)
    if args.pending_max_workers is not None:
        os.environ["MATCHY_PENDING_MAX_WORKERS"] = str(args.pending_max_workers)


#R010: Startup profiling log emission is gated by the --profile flag.
def _startup_log(start_time_seconds: float, phase: str, details: str = "", profile_enabled: bool = False) -> None:
    if profile_enabled:
        elapsed_seconds = perf_counter() - start_time_seconds
        suffix = f" | {details}" if details else ""
        print(f"[matchy-startup +{elapsed_seconds:7.3f}s] {phase}{suffix}", flush=True)


#R015: Resolve the runtime engine, defaulting to the C++ core with a Python opt-out.
def _resolve_engine(args: argparse.Namespace) -> str:
    engine = (args.engine or os.environ.get("MATCHY_ENGINE", DEFAULT_ENGINE)).strip().lower()
    if engine not in {"cpp", "python"}:
        engine = DEFAULT_ENGINE
    return engine


#R015: Build the C++ matchycore tool on demand so the cutover entrypoint is self-contained.
def _ensure_cpp_binary(repo_root: str, target: str) -> str:
    core_dir = os.path.join(repo_root, "src", "core")
    build_dir = os.path.join(core_dir, "build")
    binary = os.path.join(build_dir, target)
    if not os.path.isfile(binary):
        subprocess.run(["cmake", "-S", core_dir, "-B", build_dir, _CMAKE_BUILD_TYPE_ARG], check=True)
        subprocess.run(["cmake", "--build", build_dir, "--target", target, "-j", str(os.cpu_count() or 4)], check=True)
    if not os.path.isfile(binary):
        raise SystemExit(f"Failed to build C++ {target} at {binary}")
    return binary


#R015: Translate the parsed launcher flags into the C++ matchy_api argument vector.
def _cpp_api_passthrough(args: argparse.Namespace) -> list[str]:
    passthrough = ["--host", str(args.host), "--port", str(args.port)]
    if args.profile:
        passthrough.append("--profile")
    if args.port_guard is True:
        passthrough.append("--port-guard")
    if args.port_guard is False:
        passthrough.append("--no-port-guard")
    if args.mailcart_body_enrichment is not None:
        passthrough += ["--mailcart-body-enrichment", args.mailcart_body_enrichment]
    if args.mailcart_body_enrichment_limit is not None:
        passthrough += ["--mailcart-body-enrichment-limit", str(args.mailcart_body_enrichment_limit)]
    if args.mailcart_body_enrichment_timeout_seconds is not None:
        passthrough += ["--mailcart-body-enrichment-timeout-seconds", str(args.mailcart_body_enrichment_timeout_seconds)]
    if args.mailcart_body_enrichment_max_workers is not None:
        passthrough += ["--mailcart-body-enrichment-max-workers", str(args.mailcart_body_enrichment_max_workers)]
    if args.mailcart_get_message_timeout_seconds is not None:
        passthrough += ["--mailcart-get-message-timeout-seconds", str(args.mailcart_get_message_timeout_seconds)]
    if args.pending_max_workers is not None:
        passthrough += ["--pending-max-workers", str(args.pending_max_workers)]
    return passthrough


#R015: Hand off to the authoritative C++ matchy_api binary, mirroring the launcher's flag contract.
def _exec_cpp_api(args: argparse.Namespace) -> None:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    binary = _ensure_cpp_binary(repo_root, "matchy_api")
    os.execv(binary, [binary, *_cpp_api_passthrough(args)])


if __name__ == "__main__":
    startup_started_at = perf_counter()
    args = _parse_args()
    if _resolve_engine(args) == "cpp":
        _exec_cpp_api(args)
    os.environ["MATCHY_STARTUP_LOG"] = "true" if args.profile else "false"
    os.environ["MATCHY_RUNTIME_PROFILE"] = "true" if args.profile else "false"
    existing_api_auth_token = os.environ.get("MATCHY_API_AUTH_TOKEN", "").strip()
    if not existing_api_auth_token:
        os.environ["MATCHY_API_AUTH_TOKEN"] = DEFAULT_API_AUTH_TOKEN
        _startup_log(startup_started_at, "api-auth-token-defaulted", profile_enabled=args.profile)
    _startup_log(startup_started_at, "script-start", f"pid={os.getpid()}", profile_enabled=args.profile)
    _startup_log(startup_started_at, "args-parsed", f"host={args.host} port={args.port}", profile_enabled=args.profile)
    _apply_argument_overrides(args)
    _startup_log(startup_started_at, "env-overrides-applied", profile_enabled=args.profile)
    guard_enabled = os.environ.get("MATCHY_PORT_GUARD", "true").lower() == "true"
    if args.port_guard is not None:
        guard_enabled = args.port_guard
    _startup_log(startup_started_at, "port-guard-evaluated", f"enabled={str(guard_enabled).lower()}", profile_enabled=args.profile)
    if guard_enabled and _is_port_in_use(args.host, args.port):
        _startup_log(startup_started_at, "port-in-use-detected", f"{args.host}:{args.port}", profile_enabled=args.profile)
        if _is_matchy_healthy(args.host, args.port):
            _startup_log(startup_started_at, "existing-matchy-healthy", "reusing-running-process", profile_enabled=args.profile)
            print(f"Matchy API already running on {args.host}:{args.port}; reusing existing process.")
            raise SystemExit(0)
        raise SystemExit(f"Port {args.port} is already in use by another process.")
    create_app_import_started_at = perf_counter()
    _startup_log(startup_started_at, "importing-create-app", profile_enabled=args.profile)
    from matchy.api import create_app
    _startup_log(
        startup_started_at,
        "create-app-imported",
        f"phase_elapsed={perf_counter() - create_app_import_started_at:7.3f}s",
        profile_enabled=args.profile,
    )
    app_creation_started_at = perf_counter()
    _startup_log(startup_started_at, "creating-fastapi-app", profile_enabled=args.profile)
    app = create_app()
    _startup_log(
        startup_started_at,
        "fastapi-app-created",
        f"phase_elapsed={perf_counter() - app_creation_started_at:7.3f}s",
        profile_enabled=args.profile,
    )
    #R005: Launch local API server on deterministic host/port.
    _startup_log(startup_started_at, "starting-uvicorn", f"host={args.host} port={args.port}", profile_enabled=args.profile)
    uvicorn.run(app, host=args.host, port=args.port)
