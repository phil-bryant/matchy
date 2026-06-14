#!/usr/bin/env bats

@test "matchycore mailcart scope has scoped requirement tags" {
  #R001: Matchycore mailcart shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/mailcart.hpp src/core/src/mailcart.cpp
  [ "$status" -eq 0 ]
}
