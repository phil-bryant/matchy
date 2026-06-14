#!/usr/bin/env bats

@test "matchycore scoring scope has scoped requirement tags" {
  #R001: Matchycore scoring shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/scoring.hpp src/core/src/scoring.cpp
  [ "$status" -eq 0 ]
}
