#!/usr/bin/env bats

@test "matchycore models scope has scoped requirement tags" {
  #R001: Matchycore models shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/models.hpp
  [ "$status" -eq 0 ]
}
