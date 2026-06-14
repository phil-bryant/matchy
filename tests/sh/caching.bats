#!/usr/bin/env bats

@test "matchycore caching scope has scoped requirement tags" {
  #R001: Matchycore caching shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/caching.hpp src/core/src/caching.cpp
  [ "$status" -eq 0 ]
}
