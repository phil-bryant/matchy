# t15 run cpp core unit tests Requirements

## Scope

Applies to `tests/t15_run_cpp_core_unit_tests.sh`, the self-contained matchy-owned
C++ core lane that builds `matchycore` and runs its Catch2 unit suite. There is
no runner delegation: the C++ core is matchy-owned (thick lane).

R001  Statement: Lane configures and builds the matchy C++ core in RelWithDebInfo.
Design: Run `cmake -S src/core -B src/core/build -DCMAKE_BUILD_TYPE=RelWithDebInfo` then `cmake --build` with host parallelism.
Tests:
- R001-T01: Verify the lane configures (RelWithDebInfo) and builds the C++ core.

R005  Statement: Lane runs the Catch2 C++ core unit suite.
Design: Execute the built `matchycore_tests` binary and report a passing marker.
Tests:
- R005-T01: Verify the lane runs `matchycore_tests` and reports a passing marker.
