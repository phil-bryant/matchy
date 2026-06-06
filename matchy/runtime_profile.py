from __future__ import annotations

import os


#R065: Gate verbose per-phase runtime instrumentation behind MATCHY_RUNTIME_PROFILE so the matchy
#R065: auto-driver can emit on-demand timing breadcrumbs without polluting normal (unset) runs.
def _runtime_profile_enabled() -> bool:
    enabled = os.environ.get("MATCHY_RUNTIME_PROFILE", "false").strip().lower() == "true"
    return enabled


#R065: Emit a single stdout profiling breadcrumb line only when runtime profiling is enabled.
def _runtime_profile_log(phase: str, details: str = "") -> None:
    if _runtime_profile_enabled():
        suffix = f" | {details}" if details else ""
        print(f"[matchy-runtime] {phase}{suffix}", flush=True)
