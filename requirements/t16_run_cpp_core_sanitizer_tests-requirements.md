# t16 run cpp core sanitizer tests Requirements

## Scope

Applies to `tests/t16_run_cpp_core_sanitizer_tests.sh`, the self-contained
matchy-owned lane that rebuilds the C++ core with ASan+UBSan and reruns the unit
suite. There is no runner delegation: the C++ core is matchy-owned (thick lane).

R001  Statement: Lane rebuilds the C++ core with ASan+UBSan in a lane-private build tree.
Design: Configure with `-DCMAKE_BUILD_TYPE=Debug -DMATCHYCORE_SANITIZE=ON -DMATCHYCORE_BUILD_TOOLS=OFF` into `build-asan`, then build.
Tests:
- R001-T01: Verify the lane configures a sanitizer build (`MATCHYCORE_SANITIZE=ON`, Debug) and builds it.

R005  Statement: Lane reruns the unit suite under sanitizers with halt-on-error.
Design: Run `matchycore_tests` with `UBSAN_OPTIONS=halt_on_error=1` so memory-safety defects fail the lane.
Tests:
- R005-T01: Verify the lane runs the suite with `UBSAN_OPTIONS=halt_on_error=1`.
