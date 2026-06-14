#!/usr/bin/env bats

@test "matchycore version scope has scoped requirement tags" {
  #R001: Matchycore version shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/version.hpp src/core/src/version.cpp
  [ "$status" -eq 0 ]
}
