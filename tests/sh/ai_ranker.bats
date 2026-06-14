#!/usr/bin/env bats

@test "matchycore ai_ranker scope has scoped requirement tags" {
  #R001: Matchycore ai_ranker shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/include/matchycore/ai_ranker.hpp src/core/src/ai_ranker.cpp
  [ "$status" -eq 0 ]
}
