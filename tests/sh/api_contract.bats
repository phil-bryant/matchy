#!/usr/bin/env bats

@test "matchycore api_contract scope has scoped requirement tags" {
  #R001: Matchycore api_contract shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/api_contract.hpp
  [ "$status" -eq 0 ]
}
