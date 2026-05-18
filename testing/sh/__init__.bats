#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01

@test "matchy package exposes non-empty module docstring" {
  #R001: Package marker docstring is present for module introspection.
  #R001-T01: Validate non-empty package docstring.
  run env PYTHONPATH="$(pwd)" python3 -c "import matchy; print(bool((matchy.__doc__ or '').strip()))"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
