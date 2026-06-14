#!/usr/bin/env bats

@test "matchycore match_service scope has scoped requirement tags" {
  #R001: Matchycore match_service shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/match_service.hpp src/core/src/match_service.cpp
  [ "$status" -eq 0 ]
}
