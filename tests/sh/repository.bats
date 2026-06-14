#!/usr/bin/env bats

@test "matchycore repository scope has scoped requirement tags" {
  #R001: Matchycore repository shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/repository.hpp src/core/src/repository.cpp src/core/src/match_writer.cpp
  [ "$status" -eq 0 ]
}
