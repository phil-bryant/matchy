// Port of the env-resolution contracts from tests/py/test_settings.py.
#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include <cstdlib>
#include "matchycore/settings.hpp"

using Catch::Approx;
using matchycore::Settings;

namespace
{ class EnvGuard
 { public:
  EnvGuard(const char *name, const char *value) : name_(name)
  { const char *old_value = std::getenv(name);
   if (old_value != nullptr) old_ = old_value;
   had_old_ = old_value != nullptr;
   if (value != nullptr) ::setenv(name, value, 1);
   else ::unsetenv(name);
  }

  ~EnvGuard()
  { if (had_old_) ::setenv(name_.c_str(), old_.c_str(), 1);
   else ::unsetenv(name_.c_str());
  }

  private:
  std::string name_, old_;
  bool had_old_ = false;
 };
}

TEST_CASE("defaults mirror the python dataclass", "[settings]")
{ Settings s;
 REQUIRE(s.mailcart_service_base_url() == "https://127.0.0.1:8788");
 REQUIRE(s.mailcart_body_enrichment_enabled());
 REQUIRE(s.mailcart_body_enrichment_limit() == 75);
 REQUIRE(s.mailcart_get_message_timeout_seconds() == 3);
 REQUIRE(s.mailcart_search_timeout_seconds() == 45);
 REQUIRE(s.anthropic_model() == "claude-sonnet-4-5");
 REQUIRE(s.openai_model() == "gpt-4.1-mini");
 REQUIRE(s.auto_confirm_threshold() == Approx(0.90));
 REQUIRE(s.write_enabled());
 REQUIRE_FALSE(s.email_move_enabled());
 REQUIRE(s.near_duplicate_max_hamming_distance() == 0);
 REQUIRE(s.cldr_currencies_refresh_enabled());
 REQUIRE(s.cldr_currencies_refresh_timeout_seconds() == 5);
}

TEST_CASE("environment overrides apply", "[settings]")
{ EnvGuard base("MAILCART_SERVICE_BASE_URL", "https://10.0.0.5:9999");
 EnvGuard token("MATCHY_API_AUTH_TOKEN", "  secret  ");
 EnvGuard enrich("MATCHY_MAILCART_BODY_ENRICHMENT", "false");
 EnvGuard limit("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT", "10");
 EnvGuard write_flag("MATCHY_WRITE_ENABLED", "FALSE");
 EnvGuard move_flag("MATCHY_EMAIL_MOVE_ENABLED", "true");
 EnvGuard threshold("MATCHY_AUTO_CONFIRM_THRESHOLD", "0.75");
 EnvGuard model("MATCHY_ANTHROPIC_MODEL", "   ");
 EnvGuard anthropic_key("ANTHROPIC_API_KEY", " key-a ");
 EnvGuard anthropic_item("MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM", "");
 EnvGuard openai_key("OPENAI_API_KEY", "");
 EnvGuard openai_item("MATCHY_OPENAI_API_KEY_1PSA_ITEM", "");
 EnvGuard mailcart_token("MAILCART_SERVICE_TOKEN", "svc-token");
 Settings s = Settings::FromEnvironment();
 REQUIRE(s.mailcart_service_base_url() == "https://10.0.0.5:9999");
 REQUIRE(s.matchy_api_auth_token() == "secret");
 REQUIRE_FALSE(s.mailcart_body_enrichment_enabled());
 REQUIRE(s.mailcart_body_enrichment_limit() == 10);
 REQUIRE_FALSE(s.write_enabled());
 REQUIRE(s.email_move_enabled());
 REQUIRE(s.auto_confirm_threshold() == Approx(0.75));
 REQUIRE(s.anthropic_model() == "claude-sonnet-4-5"); // blank override falls back
 REQUIRE(s.anthropic_api_key() == "key-a");
 REQUIRE(s.mailcart_service_token() == "svc-token");
}

TEST_CASE("write token fallback chain prefers classy token", "[settings]")
{ EnvGuard mailcart_token("MAILCART_SERVICE_TOKEN", nullptr);
 EnvGuard classy_token("CLASSY_WRITE_TOKEN", "classy-token");
 EnvGuard anthropic_item("MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM", "");
 EnvGuard openai_item("MATCHY_OPENAI_API_KEY_1PSA_ITEM", "");
 Settings s = Settings::FromEnvironment();
 REQUIRE(s.mailcart_service_token() == "classy-token");
 REQUIRE(std::string(std::getenv("MAILCART_SERVICE_TOKEN")) == "classy-token");
}
