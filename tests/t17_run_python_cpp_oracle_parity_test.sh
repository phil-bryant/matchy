#!/usr/bin/env bash
# Oracle parity lane (M6): drives every deterministic scenario through BOTH the
# Python reference (matchy.scoring / caching / near_duplicate / cldr_cache via
# matchy-venv) and the C++ core (matchy_oracle_runner), diffing normalized JSON.
# Self-contained (no runner delegation): the C++ core is matchy-owned.
set -euo pipefail
umask 007

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CORE_DIR="${REPO_ROOT}/src/core"
# Lane-private build tree: parallel lanes must not race t15's cmake configure.
BUILD_DIR="${CORE_DIR}/build-parity"
VENV_PY="${REPO_ROOT}/matchy-venv/bin/python3"

#R001: Require the matchy-venv interpreter before running parity (exit 2 with remediation otherwise).
if [[ ! -x "${VENV_PY}" ]]; then
  echo "t17: matchy-venv missing (run ./02_create_venv.sh && ./04_load_requirements.sh)" >&2
  exit 2
fi

#R005: Build the C++ oracle runner target in a lane-private build tree.
cmake -S "${CORE_DIR}" -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE=RelWithDebInfo >/dev/null
cmake --build "${BUILD_DIR}" -j "$(sysctl -n hw.ncpu)" --target matchy_oracle_runner >/dev/null

#R010: Diff normalized JSON scenarios between the Python reference and the C++ oracle runner.
"${VENV_PY}" "${CORE_DIR}/oracle/compare_oracle.py" \
  --runner "${BUILD_DIR}/matchy_oracle_runner"
echo "t17: Python/C++ oracle parity passed"
