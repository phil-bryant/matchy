#!/usr/bin/env bats

@test "matchycore timeutil scope has scoped requirement tags" {
  #R001: Matchycore timeutil shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/timeutil.hpp src/core/src/timeutil.cpp
  [ "$status" -eq 0 ]
}
