#!/usr/bin/env bats

@test "matchycore matchy_driver scope has scoped requirement tags" {
  #R001: Matchycore matchy_driver shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/tools/matchy_driver.cpp
  [ "$status" -eq 0 ]
}
