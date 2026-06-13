#!/usr/bin/env bash
# C++ core lane: configure + build matchycore and run the Catch2 unit suite.
# Self-contained (no runner delegation): the C++ core is matchy-owned.
set -euo pipefail
umask 007

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CORE_DIR="${REPO_ROOT}/src/core"
BUILD_DIR="${CORE_DIR}/build"

cmake -S "${CORE_DIR}" -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE=RelWithDebInfo >/dev/null
cmake --build "${BUILD_DIR}" -j "$(sysctl -n hw.ncpu)" >/dev/null
"${BUILD_DIR}/matchycore_tests"
echo "t15: C++ core unit tests passed"
