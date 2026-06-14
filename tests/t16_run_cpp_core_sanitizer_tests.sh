#!/usr/bin/env bash
# C++ core sanitizer lane: rebuild with ASan+UBSan and rerun the unit suite.
# Memory-safety discipline is the C++ core's substitute for Python's runtime guarantees;
# this lane is non-negotiable before any cutover (migration plan M0).
set -euo pipefail
umask 007

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CORE_DIR="${REPO_ROOT}/src/core"
BUILD_DIR="${CORE_DIR}/build-asan"

#R001: Rebuild the C++ core with ASan+UBSan enabled (Debug, tools off) in a lane-private build tree.
cmake -S "${CORE_DIR}" -B "${BUILD_DIR}" \
  -DCMAKE_BUILD_TYPE=Debug -DMATCHYCORE_SANITIZE=ON -DMATCHYCORE_BUILD_TOOLS=OFF >/dev/null
cmake --build "${BUILD_DIR}" -j "$(sysctl -n hw.ncpu)" >/dev/null
#R005: Rerun the unit suite under sanitizers with halt-on-error so memory-safety defects fail the lane.
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "${BUILD_DIR}/matchycore_tests"
echo "t16: C++ core sanitizer tests passed"
