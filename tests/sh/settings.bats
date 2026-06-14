#!/usr/bin/env bats

@test "matchycore settings scope has scoped requirement tags" {
  #R001: Matchycore settings shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/settings.hpp src/core/src/settings.cpp
  [ "$status" -eq 0 ]
}
