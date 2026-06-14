#!/usr/bin/env bats

@test "matchycore near_duplicate scope has scoped requirement tags" {
  #R001: Matchycore near_duplicate shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/near_duplicate.hpp src/core/src/near_duplicate.cpp
  [ "$status" -eq 0 ]
}
