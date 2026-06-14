#!/usr/bin/env bats

@test "matchycore matchy_api scope has scoped requirement tags" {
  #R001: Matchycore matchy_api shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/tools/matchy_api.cpp
  [ "$status" -eq 0 ]
}
