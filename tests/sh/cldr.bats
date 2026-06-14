#!/usr/bin/env bats

@test "matchycore cldr scope has scoped requirement tags" {
  #R001: Matchycore cldr shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/cldr.hpp src/core/src/cldr.cpp
  [ "$status" -eq 0 ]
}
