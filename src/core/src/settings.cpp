#include "matchycore/settings.hpp"
#include <cstdlib>
#include <fstream>
#include <map>
#include <stdexcept>
#include "tellercore/onepsa.hpp"

// Port of matchy/settings.py env/1psa resolution. Teller DB credentials are intentionally absent:
// the C++ repository binds to tellercore's profile-driven engine, which resolves them itself.
namespace matchycore
{ namespace
 { std::string Strip(const std::string &value)
  { std::size_t begin = value.find_first_not_of(" \t\n\r\f\v");
   std::string out;
   if (begin != std::string::npos) out = value.substr(begin, value.find_last_not_of(" \t\n\r\f\v") - begin + 1);
   return out;
  }

  std::string GetEnv(const char *name, const std::string &fallback = "")
  { const char *raw = std::getenv(name);
   return raw == nullptr ? fallback : std::string(raw);
  }

  std::string Lower(const std::string &value)
  { std::string out = value;
   for (char &c : out)
    if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
   return out;
  }

  //R905: int((env or "<default>").strip() or "<default>") semantics; invalid integers fail startup like Python.
  int EnvInt(const char *name, int fallback)
  { std::string raw = Strip(GetEnv(name));
   int result = fallback;
   if (!raw.empty())
   { std::size_t consumed = 0;
    result = std::stoi(raw, &consumed);
    if (consumed != raw.size()) throw std::runtime_error(std::string("invalid integer for ") + name + ": " + raw);
   }
   return result;
  }

  double EnvDouble(const char *name, double fallback)
  { std::string raw = Strip(GetEnv(name));
   double result = fallback;
   if (!raw.empty())
   { char *end = nullptr;
    result = std::strtod(raw.c_str(), &end);
    if (end != raw.c_str() + raw.size())
     throw std::runtime_error(std::string("invalid number for ") + name + ": " + raw);
   }
   return result;
  }

  bool EnvBool(const char *name, bool fallback)
  { std::string raw = GetEnv(name);
   bool result = fallback;
   if (!raw.empty()) result = Lower(Strip(raw)) == "true";
   return result;
  }

  //R890: Parse ~/.env key-value lines (including export syntax).
  std::map<std::string, std::string> ReadHomeEnvFile()
  { std::map<std::string, std::string> values;
   const char *home = std::getenv("HOME");
   if (home != nullptr)
   { std::ifstream in(std::string(home) + "/.env");
    std::string line;
    while (std::getline(in, line))
    { std::string stripped = Strip(line);
     if (!stripped.empty() && stripped[0] != '#')
     { if (stripped.rfind("export ", 0) == 0) stripped = Strip(stripped.substr(7));
      std::size_t eq = stripped.find('=');
      if (eq != std::string::npos)
      { std::string key = Strip(stripped.substr(0, eq));
       std::string value = Strip(stripped.substr(eq + 1));
       while (!value.empty() && (value.front() == '"' || value.front() == '\'')) value.erase(value.begin());
       while (!value.empty() && (value.back() == '"' || value.back() == '\'')) value.pop_back();
       if (!key.empty()) values[key] = value;
      }
     }
    }
   }
   return values;
  }

  bool ValidRefChar(char c)
  { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
    || c == '.' || c == '_' || c == '-';
  }

  bool ValidRefSegment(const std::string &segment)
  { bool ok = !segment.empty();
   for (char c : segment)
    if (!ValidRefChar(c)) ok = false;
   return ok;
  }

  //R895: Resolve an optional 1psa secret (item -> password field; item/field; op://vault/item/field).
  std::string LoadOptionalSecretFrom1psa(const std::string &secret_ref)
  { std::string output;
   std::string candidate = Strip(secret_ref);
   std::string item, field;
   if (candidate.rfind("op://", 0) == 0)
   { std::string remainder = candidate.substr(5);
    std::vector<std::string> parts;
    std::string current;
    for (char c : remainder)
    { if (c == '/')
     { parts.push_back(current);
      current.clear();
     }
     else current.push_back(c);
    }
    parts.push_back(current);
    if (parts.size() == 3 && ValidRefSegment(parts[0]) && ValidRefSegment(parts[1]) && ValidRefSegment(parts[2]))
    { item = parts[1];
     field = parts[2];
    }
   }
   else
   { std::size_t slash = candidate.find('/');
    if (slash == std::string::npos)
    { if (ValidRefSegment(candidate))
     { item = candidate;
      field = "password";
     }
    }
    else
    { std::string left = candidate.substr(0, slash), right = candidate.substr(slash + 1);
     if (ValidRefSegment(left) && ValidRefSegment(right))
     { item = left;
      field = right;
     }
    }
   }
   if (!item.empty()) output = Strip(tellercore::onepsa::read_field(item, field));
   return output;
  }

  //R895: Env-var precedence with tolerant 1psa fallback for AI keys.
  std::string ResolveOptionalApiKey(const std::string &env_value, const std::string &item_name)
  { std::string resolved = Strip(env_value);
   if (resolved.empty() && !Strip(item_name).empty()) resolved = LoadOptionalSecretFrom1psa(Strip(item_name));
   return resolved;
  }

  //R880: Mailcart token: env precedence, then ~/.env fallback chain.
  std::string ResolveMailcartServiceToken()
  { std::string token = Strip(GetEnv("MAILCART_SERVICE_TOKEN"));
   if (token.empty()) token = Strip(GetEnv("CLASSY_WRITE_TOKEN"));
   if (token.empty()) token = Strip(GetEnv("TELLER_CLASSIFIER_WRITE_TOKEN"));
   if (token.empty())
   { std::map<std::string, std::string> env_values = ReadHomeEnvFile();
    for (const char *key : {"MAILCART_SERVICE_TOKEN", "CLASSY_WRITE_TOKEN", "TELLER_CLASSIFIER_WRITE_TOKEN"})
     if (token.empty() && env_values.count(key) > 0) token = Strip(env_values[key]);
   }
   return token;
  }
 }

 Settings Settings::FromEnvironment()
 { Settings s;
  s.set_mailcart_service_base_url(GetEnv("MAILCART_SERVICE_BASE_URL", "https://127.0.0.1:8788"));
  s.set_matchy_api_auth_token(Strip(GetEnv("MATCHY_API_AUTH_TOKEN")));
  s.set_mailcart_body_enrichment_enabled(EnvBool("MATCHY_MAILCART_BODY_ENRICHMENT", true));
  s.set_mailcart_body_enrichment_limit(EnvInt("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT", 75));
  s.set_mailcart_body_enrichment_timeout_seconds(EnvInt("MATCHY_MAILCART_BODY_ENRICHMENT_TIMEOUT_SECONDS", 12));
  s.set_mailcart_body_enrichment_max_workers(EnvInt("MATCHY_MAILCART_BODY_ENRICHMENT_MAX_WORKERS", 12));
  s.set_mailcart_get_message_timeout_seconds(EnvInt("MATCHY_MAILCART_GET_MESSAGE_TIMEOUT_SECONDS", 3));
  s.set_mailcart_failure_cooldown_seconds(EnvInt("MATCHY_MAILCART_FAILURE_COOLDOWN_SECONDS", 15));
  s.set_mailcart_search_date_window_days(EnvInt("MATCHY_MAILCART_SEARCH_DATE_WINDOW_DAYS", 45));
  s.set_mailcart_search_timeout_seconds(EnvInt("MATCHY_MAILCART_SEARCH_TIMEOUT_SECONDS", 45));
  s.set_mailcart_ca_bundle(GetEnv("MATCHY_MAILCART_CA_BUNDLE"));
  s.set_mailcart_startup_healthcheck_enabled(EnvBool("MATCHY_MAILCART_STARTUP_HEALTHCHECK", true));
  s.set_mailcart_startup_healthcheck_timeout_seconds(EnvInt("MATCHY_MAILCART_STARTUP_HEALTHCHECK_TIMEOUT_SECONDS", 2));
  s.set_anthropic_api_key_item(GetEnv("MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM", "anthropic_api_key"));
  s.set_openai_api_key_item(GetEnv("MATCHY_OPENAI_API_KEY_1PSA_ITEM", "openai_api_key"));
  std::string anthropic_model = Strip(GetEnv("MATCHY_ANTHROPIC_MODEL"));
  s.set_anthropic_model(anthropic_model.empty() ? "claude-sonnet-4-5" : anthropic_model);
  s.set_openai_model(GetEnv("MATCHY_OPENAI_MODEL", "gpt-4.1-mini"));
  s.set_auto_confirm_threshold(EnvDouble("MATCHY_AUTO_CONFIRM_THRESHOLD", 0.90));
  s.set_write_enabled(Lower(Strip(GetEnv("MATCHY_WRITE_ENABLED", "true"))) == "true");
  s.set_email_move_enabled(Lower(Strip(GetEnv("MATCHY_EMAIL_MOVE_ENABLED", "false"))) == "true");
  s.set_near_duplicate_max_hamming_distance(EnvInt("MATCHY_NEAR_DUPLICATE_MAX_HAMMING_DISTANCE", 0));
  std::string default_cache = GetEnv("HOME") + std::string("/.cache/matchy/cldr-currencies-en.json");
  s.set_cldr_currencies_cache_path(GetEnv("MATCHY_CLDR_CURRENCIES_CACHE_PATH", default_cache));
  s.set_cldr_currencies_refresh_enabled(EnvBool("MATCHY_CLDR_CURRENCIES_REFRESH_ENABLED", true));
  s.set_cldr_currencies_refresh_timeout_seconds(EnvInt("MATCHY_CLDR_CURRENCIES_REFRESH_TIMEOUT_SECONDS", 5));
  std::string mailcart_token = ResolveMailcartServiceToken();
  s.set_mailcart_service_token(mailcart_token);
  if (!mailcart_token.empty() && Strip(GetEnv("MAILCART_SERVICE_TOKEN")).empty())
   ::setenv("MAILCART_SERVICE_TOKEN", mailcart_token.c_str(), 1);
  s.set_anthropic_api_key(ResolveOptionalApiKey(GetEnv("ANTHROPIC_API_KEY"), s.anthropic_api_key_item()));
  s.set_openai_api_key(ResolveOptionalApiKey(GetEnv("OPENAI_API_KEY"), s.openai_api_key_item()));
  return s;
 }
}
