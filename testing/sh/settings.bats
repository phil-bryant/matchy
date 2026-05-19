#!/usr/bin/env bats

load "helpers/common.bash"

setup() {
  setup_shell_test
  export SETTINGS_PROBE="${TEST_TMPDIR}/settings_probe.py"
  cat > "${SETTINGS_PROBE}" <<'EOF'
#!/usr/bin/env python3
import sys
from matchy.settings import Settings
field = sys.argv[1] if len(sys.argv) > 1 else "teller_db_password"
print(getattr(Settings(), field))
EOF
  chmod 770 "${SETTINGS_PROBE}"
}

teardown() {
  teardown_shell_test
}

stub_1psa_routed() {
  # Route 1psa stubs by item name so both the required teller secret and the optional AI keys can resolve in one test.
  stub_cmd 1psa "$1"
}

@test "loads teller password from default 1psa item when no refs are set" {
  #R001: Default 1psa item resolves teller password without password env vars.
  #R001-T01: Default-item teller password resolution.
  stub_cmd 1psa 'if [ "$1" = "-p" ] && [ "$2" = "localhost_postgres_teller" ]; then echo "secret-default"; exit 0; fi; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}"
  [ "$status" -eq 0 ]
  [ "$output" = "secret-default" ]
}

@test "loads teller password through 1psa item reference override" {
  #R005: Item-name override is resolved through 1psa -p.
  #R005-T01: Item-name override resolution.
  stub_cmd 1psa 'if [ "$1" = "-p" ] && [ "$2" = "custom_item" ]; then echo "secret-from-1psa"; exit 0; fi; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="custom_item" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}"
  [ "$status" -eq 0 ]
  [ "$output" = "secret-from-1psa" ]
}

@test "loads teller password through 1psa read for op references" {
  #R005: op:// references are resolved through 1psa read.
  #R005-T02: op:// reference resolution via 1psa read.
  stub_cmd 1psa 'if [ "$1" = "read" ] && [ "$2" = "op://vault/item/password" ]; then echo "secret-op-ref"; exit 0; fi; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" OP_SERVICE_ACCOUNT_TOKEN="token-ok" TELLER_DB_PASSWORD_1PSA_REF="op://vault/item/password" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}"
  [ "$status" -eq 0 ]
  [ "$output" = "secret-op-ref" ]
}

@test "fails clearly when 1psa lookup fails" {
  #R010: 1psa lookup failures produce explicit runtime errors.
  #R010-T01: Failing 1psa lookup raises clear error.
  stub_cmd 1psa 'echo "boom" >&2; exit 9'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" OP_SERVICE_ACCOUNT_TOKEN="token-ok" TELLER_DB_PASSWORD_1PSA_REF="op://vault/item/password" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}"
  [ "$status" -ne 0 ]
  [[ "$output" == *"1psa failed to resolve TELLER_DB_PASSWORD_1PSA_REF"* ]]
}

@test "fails clearly when op token is invalid for 1psa auth" {
  #R010: Invalid OP service-account token returns targeted auth guidance.
  #R010-T02: Service-account auth-failure raises targeted guidance.
  stub_cmd 1psa 'echo "Failed to create client: Post \"https://my.1password.com/api/v3/auth/start?\": Forbidden" >&2; exit 1'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" OP_SERVICE_ACCOUNT_TOKEN="token-bad" TELLER_DB_PASSWORD_1PSA_REF="localhost_postgres_teller" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}"
  [ "$status" -ne 0 ]
  [[ "$output" == *"1psa authentication failed for OP_SERVICE_ACCOUNT_TOKEN"* ]]
}

@test "loads anthropic api key from 1psa item when env var is unset" {
  #R015: Anthropic key resolves from default 1psa item `anthropic_api_key` when ANTHROPIC_API_KEY env var is unset.
  #R015-T01: Anthropic 1psa item resolution.
  stub_1psa_routed '
case "$2" in
  localhost_postgres_teller) echo "secret-teller"; exit 0 ;;
  anthropic_api_key) echo "secret-claude"; exit 0 ;;
  openai_api_key) echo "secret-gpt"; exit 0 ;;
esac
exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}" anthropic_api_key
  [ "$status" -eq 0 ]
  [ "$output" = "secret-claude" ]
}

@test "loads openai api key fallback from 1psa item when env var is unset" {
  #R015: OpenAI fallback key resolves from default 1psa item `openai_api_key` when OPENAI_API_KEY env var is unset.
  #R015-T02: OpenAI fallback 1psa item resolution.
  stub_1psa_routed '
case "$2" in
  localhost_postgres_teller) echo "secret-teller"; exit 0 ;;
  anthropic_api_key) echo "secret-claude"; exit 0 ;;
  openai_api_key) echo "secret-gpt"; exit 0 ;;
esac
exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}" openai_api_key
  [ "$status" -eq 0 ]
  [ "$output" = "secret-gpt" ]
}

@test "env var override beats 1psa for anthropic key" {
  #R015: ANTHROPIC_API_KEY env var overrides any 1psa-resolved anthropic key value.
  #R015-T03: Env var override beats 1psa for anthropic key.
  stub_1psa_routed '
case "$2" in
  localhost_postgres_teller) echo "secret-teller"; exit 0 ;;
  anthropic_api_key) echo "secret-claude-from-1psa"; exit 0 ;;
esac
exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="env-claude" OPENAI_API_KEY="" "${SETTINGS_PROBE}" anthropic_api_key
  [ "$status" -eq 0 ]
  [ "$output" = "env-claude" ]
}

@test "tolerates missing AI keys in 1psa and keeps settings constructible" {
  #R015: Missing AI items in 1psa resolve to empty strings without failing Settings construction.
  #R015-T04: Missing AI items in 1psa keep settings constructible.
  stub_1psa_routed '
case "$2" in
  localhost_postgres_teller) echo "secret-teller"; exit 0 ;;
esac
echo "item not found" >&2
exit 5'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}" anthropic_api_key
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "mailcart body enrichment flags default to enabled and limit 75" {
  #R030: Default Mailcart body-enrichment feature flag is enabled with a sane default limit.
  #R030-T01: Verify mailcart_body_enrichment_enabled is True and limit is 75 with no env overrides.
  stub_1psa_routed 'case "$2" in localhost_postgres_teller) echo "secret-teller"; exit 0 ;; esac; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" MATCHY_MAILCART_BODY_ENRICHMENT="" MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT="" "${SETTINGS_PROBE}" mailcart_body_enrichment_enabled
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" "${SETTINGS_PROBE}" mailcart_body_enrichment_limit
  [ "$status" -eq 0 ]
  [ "$output" = "75" ]
}

@test "default anthropic_model is the dated stable id and respects env override" {
  #R035: Anthropic model defaults to a pinned dated id; env var overrides it.
  #R035-T01: Verify default anthropic_model is claude-sonnet-4-5.
  #R035-T02: Verify MATCHY_ANTHROPIC_MODEL override is respected.
  stub_1psa_routed 'case "$2" in localhost_postgres_teller) echo "secret-teller"; exit 0 ;; esac; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" MATCHY_ANTHROPIC_MODEL="" "${SETTINGS_PROBE}" anthropic_model
  [ "$status" -eq 0 ]
  [ "$output" = "claude-sonnet-4-5" ]
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" MATCHY_ANTHROPIC_MODEL="claude-opus-x" "${SETTINGS_PROBE}" anthropic_model
  [ "$status" -eq 0 ]
  [ "$output" = "claude-opus-x" ]
}

@test "mailcart body enrichment flags honor env overrides" {
  #R030: Mailcart body-enrichment env overrides flip the flag and resize the limit.
  #R030-T02: Verify MATCHY_MAILCART_BODY_ENRICHMENT=false and ..._LIMIT=10 are reflected on Settings.
  stub_1psa_routed 'case "$2" in localhost_postgres_teller) echo "secret-teller"; exit 0 ;; esac; exit 7'
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" MATCHY_MAILCART_BODY_ENRICHMENT="false" MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT="10" "${SETTINGS_PROBE}" mailcart_body_enrichment_enabled
  [ "$status" -eq 0 ]
  [ "$output" = "False" ]
  run env PYTHONPATH="$(repo_root)" TELLER_DB_PASSWORD="" TELLER_DB_PASSWORD_1PSA_REF="" ANTHROPIC_API_KEY="" OPENAI_API_KEY="" MATCHY_MAILCART_BODY_ENRICHMENT="false" MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT="10" "${SETTINGS_PROBE}" mailcart_body_enrichment_limit
  [ "$status" -eq 0 ]
  [ "$output" = "10" ]
}
