#!/usr/bin/env bats

load "helpers/common.bash"

setup() {
  setup_shell_test
  export SETTINGS_PROBE="${TEST_TMPDIR}/settings_probe.py"
  cat > "${SETTINGS_PROBE}" <<'EOF'
#!/usr/bin/env python3
from matchy.settings import Settings
print(Settings().teller_db_password)
EOF
  chmod 770 "${SETTINGS_PROBE}"
}

teardown() {
  teardown_shell_test
}

@test "loads teller password from default 1psa item when no refs are set" {
  #R001: Default 1psa item resolves teller password without password env vars.
  stub_cmd 1psa 'if [ "$1" = "-p" ] && [ "$2" = "localhost_postgres_teller" ]; then echo "secret-default"; exit 0; fi; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" "${SETTINGS_PROBE}"
  [ "$status" -eq 0 ]
  [ "$output" = "secret-default" ]
}

@test "loads teller password through 1psa item reference override" {
  #R005: Item-name override is resolved through 1psa -p.
  stub_cmd 1psa 'if [ "$1" = "-p" ] && [ "$2" = "custom_item" ]; then echo "secret-from-1psa"; exit 0; fi; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="custom_item" "${SETTINGS_PROBE}"
  [ "$status" -eq 0 ]
  [ "$output" = "secret-from-1psa" ]
}

@test "loads teller password through 1psa read for op references" {
  #R005: op:// references are resolved through 1psa read.
  stub_cmd 1psa 'if [ "$1" = "read" ] && [ "$2" = "op://vault/item/password" ]; then echo "secret-op-ref"; exit 0; fi; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" OP_SERVICE_ACCOUNT_TOKEN="token-ok" TELLER_DB_PASSWORD_1PSA_REF="op://vault/item/password" "${SETTINGS_PROBE}"
  [ "$status" -eq 0 ]
  [ "$output" = "secret-op-ref" ]
}

@test "fails clearly when 1psa lookup fails" {
  #R010: 1psa lookup failures produce explicit runtime errors.
  stub_cmd 1psa 'echo "boom" >&2; exit 9'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" OP_SERVICE_ACCOUNT_TOKEN="token-ok" TELLER_DB_PASSWORD_1PSA_REF="op://vault/item/password" "${SETTINGS_PROBE}"
  [ "$status" -ne 0 ]
  [[ "$output" == *"1psa failed to resolve TELLER_DB_PASSWORD_1PSA_REF"* ]]
}

@test "fails clearly when op token is invalid for 1psa auth" {
  #R010: Invalid OP service-account token returns targeted auth guidance.
  stub_cmd 1psa 'echo "Failed to create client: Post \"https://my.1password.com/api/v3/auth/start?\": Forbidden" >&2; exit 1'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" OP_SERVICE_ACCOUNT_TOKEN="token-bad" TELLER_DB_PASSWORD_1PSA_REF="localhost_postgres_teller" "${SETTINGS_PROBE}"
  [ "$status" -ne 0 ]
  [[ "$output" == *"1psa authentication failed for OP_SERVICE_ACCOUNT_TOKEN"* ]]
}
