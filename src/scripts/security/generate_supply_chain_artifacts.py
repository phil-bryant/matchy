#!/usr/bin/env python3
"""Thin pointer to runner's supply-chain artifact generator."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    #R001: Resolve runner-owned generator path from matchy repo root.
    repo_root = Path(__file__).resolve().parents[3]
    runner_script = repo_root.parent / "runner" / "src" / "scripts" / "security" / "generate_supply_chain_artifacts.py"
    #R005: Fail fast with explicit error when runner generator is unavailable.
    if not runner_script.is_file():
        raise SystemExit(f"Missing runner supply-chain generator: {runner_script}")
    #R010: Preserve CLI passthrough and execute runner script as __main__.
    sys.argv = [str(runner_script), *sys.argv[1:]]
    runpy.run_path(str(runner_script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
