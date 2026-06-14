#!/usr/bin/env bats

@test "matchycore enrichment scope has scoped requirement tags" {
  #R001: Matchycore enrichment shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/enrichment.hpp src/core/src/enrichment.cpp
  [ "$status" -eq 0 ]
}
