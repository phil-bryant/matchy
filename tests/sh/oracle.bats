#!/usr/bin/env bats

@test "matchycore oracle scope has scoped requirement tags" {
  #R001: Matchycore oracle shell traceability assertion.
  #R001-T01: Scope files expose scoped #R001 tags for strict traceability checks.
  run rg -n "#R001:" src/core/oracle/compare_oracle.py src/core/tools/oracle_runner.cpp
  [ "$status" -eq 0 ]
}
