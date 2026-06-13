---
name: Matchy Python to C++ Migration
overview: "Migrate matchy's Python FastAPI matching engine to a C++20 core (`matchycore`) following the classy/teller playbook: CMake + Catch2 scaffold, bottom-up porting starting with the mutation-tested scoring wedge, oracle parity against the live Python implementation, ending with a cpp-httplib HTTP service on :8790 plus a C++ driver CLI. Python stays authoritative until parity is green."
todos:
  - id: m0-scaffold
    content: "M0: Create src/core scaffold (CMakeLists, Catch2 smoke, include/matchycore), root Makefile, t15/t16 lanes"
    status: completed
  - id: m1-scoring
    content: "M1: Port scoring_core, models, near_duplicate with Catch2 tests from test_scoring_core.py"
    status: completed
  - id: m2-mailcart
    content: "M2: Port mailcart client, search fallback chain, enrichment, cldr_cache with stubbed-server tests"
    status: completed
  - id: m3-db
    content: "M3: Port settings, repository, match_writer, caching over libtellercore.a (gated on teller build)"
    status: completed
  - id: m4-ai
    content: "M4: Port ai_ranker (Anthropic/OpenAI HTTPS, prompt v3, deterministic fallback)"
    status: completed
  - id: m5-service
    content: "M5: Port match_service orchestration, cpp-httplib API binary on :8790, C++ driver CLI"
    status: completed
  - id: m6-parity
    content: "M6: Build oracle_runner + compare_oracle.py parity harness, t17 lane, make parity"
    status: completed
  - id: m7-docs
    content: "M7: Update Architecture.md/README for dual-stack state; defer Python retirement to follow-up"
    status: completed
isProject: false
---

# Matchy Python → C++ Migration

## End State
- C++ HTTP service preserving the existing REST contract (`GET /health`, `POST /v1/matchy/runs`, `/runs/pending`, `/confirm` on `127.0.0.1:8790`, Bearer auth, rate limiting, `MATCHY_WRITE_ENABLED` gate), so classy's `make stack` and the driver keep working unchanged.
- C++ driver CLI replacing [07_run_matchy_driver.py](07_run_matchy_driver.py).
- AI ranker ported to C++ (Anthropic primary → OpenAI fallback → deterministic) via raw HTTPS with cpp-httplib.
- DB access via `libtellercore.a` (teller's in-flight C++ core) — profile resolution, SQLCipher/Postgres backends, 1psa secrets. Matchy does not duplicate that layer.
- Python source retained until oracle parity is green, then retired in a follow-up (classy's `python_oracle_retirement` pattern).

## Layout & Build (mirrors classy/teller)
- `src/core/` with `include/matchycore/*.hpp`, `src/*.cpp`, `tests/` (Catch2), `tools/`, `oracle/`, `CMakeLists.txt`.
- C++20, `-Wall -Wextra -Wpedantic -Werror`, `RelWithDebInfo`, macOS 14.0; options `MATCHYCORE_BUILD_TESTS/TOOLS`, `MATCHYCORE_SANITIZE`, `MATCHYCORE_ENABLE_HTTP`.
- Deps via FetchContent: nlohmann/json 3.11.3, Catch2 3.7.1, cpp-httplib 0.18.3 + OpenSSL; SQLCipher/libpq come through tellercore.
- Thin root `Makefile` (`core`, `test`, `sanitize`, `parity`, `run`, `clean`) per classy's [Makefile](../classy/Makefile) and the Makefile-requirements rule (timestamped Trash preservation, no `rm`, explicit permissions).
- New C++ in this repo follows matchy workspace rules (pro-style braces, `class` not `struct`, single return, structured control flow) — note this intentionally differs from classy/teller house style.

## Python → C++ module map
- `scoring_core.py`, `models.py`, `near_duplicate.py` → `scoring.cpp`, `models.hpp`, `near_duplicate.cpp` (pure logic wedge, mutation-tested today)
- `settings.py` → `settings.cpp` (env/1psa via tellercore's onepsa)
- `repository.py`, `match_writer.py`, `db_target.py` → `repository.cpp`, `match_writer.cpp` over `tellercore::db`
- `mailcart_client.py`, `search.py`, `enrichment.py`, `caching.py`, `cldr_cache.py` → `mailcart.cpp`, `search.cpp`, `enrichment.cpp`, `caching.cpp`, `cldr.cpp`
- `ai_ranker.py` → `ai_ranker.cpp` (HTTPS JSON to Anthropic/OpenAI, prompt `v3` preserved)
- `service.py` (mixin orchestration) → `match_service.cpp` (composed class, no mixins)
- `api.py` + `06_run_matchy_api.py` → `tools/matchy_api.cpp` (cpp-httplib server)
- `07_run_matchy_driver.py` → `tools/matchy_driver.cpp`

## Phases
- **M0 — Scaffold**: `src/core/` tree, CMakeLists, Catch2 smoke test, root Makefile, `tests/t15_run_cpp_core_unit_tests.sh` + `t16` sanitizer lane.
- **M1 — Scoring wedge**: port `scoring_core`/`models`/`near_duplicate`; Catch2 tests transliterated from `tests/py/test_scoring_core.py` (70 tests) and the Hypothesis property suite's invariants. No DB or HTTP needed.
- **M2 — Mailcart + enrichment + CLDR**: HTTP client, search fallback chain, body enrichment, currency cache; tests with stubbed httplib server.
- **M3 — DB layer** (gated on teller M0/M1 building): settings, repository, match_writer, caching over `libtellercore.a`; tests against SQLite mirror schema like the Python unit tests' Postgres-mode pinning. If tellercore stalls, this phase blocks — escalate rather than fork a private DB layer.
- **M4 — AI ranker**: Anthropic/OpenAI HTTPS, JSON selection contract, deterministic fallback; tests with canned responses.
- **M5 — Service + API + driver**: `match_service` orchestration, cpp-httplib API binary, driver CLI; existing pytest API tests re-pointed at the C++ server as an integration lane.
- **M6 — Oracle parity**: `tools/oracle_runner.cpp` + `compare_oracle.py` running identical scenarios through Python matchy and the C++ runner (teller M3 pattern), `tests/t17` lane, `make parity`. Freeze goldens.
- **M7 — Docs**: update [Architecture.md](Architecture.md)/README with dual-stack state; Python retirement deferred to a follow-up plan once parity is green and the driver/classy stack runs on the C++ binary.

## Verification
- `make test` → t15 Catch2 + existing Python lanes stay green throughout.
- `make sanitize` → ASan/UBSan rebuild (classy t16 pattern).
- `make parity` → Python↔C++ oracle diff must be empty before any retirement.
- Existing `./05_run_all_tests_parallel.sh` lanes remain passing — Python is untouched until M7.