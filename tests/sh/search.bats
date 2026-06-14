#!/usr/bin/env bats

@test "matchycore search scope has scoped requirement tags" {
  #R001: Matchycore search shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/search.hpp src/core/src/search.cpp
  [ "$status" -eq 0 ]
}
