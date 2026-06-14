// Port of 07_run_matchy_driver.py: poll the Matchy API's pending-run endpoint on an interval,
// printing one deterministic summary line per run. Scoped to loopback API hosts only.
#include <httplib.h>
#include <atomic>
#include <csignal>
#include <cstdlib>
#include <string>
#include <thread>
#include <vector>
#include <nlohmann/json.hpp>

namespace
{ using nlohmann::json;

 std::atomic<bool> g_interrupted{false};

// #R001: Matchycore traceability implementation coverage.
 void HandleInterrupt(int) { g_interrupted.store(true); }

// #R001: Matchycore traceability implementation coverage.
 std::string EnvOr(const char *name, const std::string &fallback)
 { const char *raw = std::getenv(name);
  return raw != nullptr && raw[0] != '\0' ? std::string(raw) : fallback;
 }

// #R001: Matchycore traceability implementation coverage.
 std::string Trim(const std::string &value)
 { std::size_t begin = value.find_first_not_of(" \t\r\n");
  std::string out;
  if (begin != std::string::npos)
  { std::size_t end = value.find_last_not_of(" \t\r\n");
   out = value.substr(begin, end - begin + 1);
  }
  return out;
 }

// #R001: Matchycore traceability implementation coverage.
 int EnvInt(const char *name, int fallback, int min_value)
 { int value = fallback;
  std::string raw = Trim(EnvOr(name, std::to_string(fallback)));
  try { int parsed = std::stoi(raw); if (parsed >= min_value) value = parsed; }
  catch (const std::exception &) { value = fallback; }
  return value;
 }

// #R001: Matchycore traceability implementation coverage.
 bool EnvBool(const char *name, bool fallback)
 { std::string raw = Trim(EnvOr(name, fallback ? "true" : "false"));
  for (char &c : raw) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  bool value = fallback;
  if (raw == "1" || raw == "true" || raw == "yes" || raw == "on") value = true;
  if (raw == "0" || raw == "false" || raw == "no" || raw == "off") value = false;
  return value;
 }

 class Config
 { public:
  std::string api_base_url = "http://127.0.0.1:8790";
  int limit = 10;
  int lookback_days = 14;
  int interval_seconds = 30;
  int timeout_seconds = 180;
  int max_runs = 0;
  std::string trigger_source = "auto";
  std::string api_auth_token = "matchy-local-dev-token";
  bool once = false;
  bool force_rematch = false;
 };

 // #R001: Keep the driver scoped to loopback hosts; returns the normalized base url.
 std::string ValidatedApiBaseUrl(const std::string &raw, std::string &error)
 { std::string candidate = Trim(raw);
  if (candidate.empty()) candidate = "http://127.0.0.1:8790";
  std::string scheme;
  std::size_t scheme_end = candidate.find("://");
  std::string host_part;
  if (scheme_end != std::string::npos)
  { scheme = candidate.substr(0, scheme_end);
   host_part = candidate.substr(scheme_end + 3);
  }
  std::string hostname = host_part.substr(0, host_part.find_first_of(":/"));
  bool scheme_ok = scheme == "http" || scheme == "https";
  bool host_ok = hostname == "127.0.0.1" || hostname == "localhost";
  std::string out;
  if (!scheme_ok) error = "MATCHY_API_BASE_URL must use http or https";
  else if (!host_ok) error = "MATCHY_API_BASE_URL host must be loopback (127.0.0.1 or localhost)";
  else
  { while (!candidate.empty() && candidate.back() == '/') candidate.pop_back();
   out = candidate;
  }
  return out;
 }

// #R001: Matchycore traceability implementation coverage.
 Config ParseArgs(int argc, char **argv)
 { Config config;
  config.api_base_url = EnvOr("MATCHY_API_BASE_URL", config.api_base_url);
  config.limit = EnvInt("MATCHY_DRIVER_LIMIT", 10, 1);
  config.lookback_days = EnvInt("MATCHY_DRIVER_LOOKBACK_DAYS", 14, 1);
  config.interval_seconds = EnvInt("MATCHY_DRIVER_INTERVAL_SECONDS", 30, 1);
  config.timeout_seconds = EnvInt("MATCHY_DRIVER_TIMEOUT_SECONDS", 180, 1);
  config.max_runs = EnvInt("MATCHY_DRIVER_MAX_RUNS", 0, 0);
  config.trigger_source = Trim(EnvOr("MATCHY_DRIVER_TRIGGER_SOURCE", "auto"));
  if (config.trigger_source.empty()) config.trigger_source = "auto";
  config.api_auth_token = Trim(EnvOr("MATCHY_API_AUTH_TOKEN", "matchy-local-dev-token"));
  if (config.api_auth_token.empty()) config.api_auth_token = "matchy-local-dev-token";
  config.once = EnvBool("MATCHY_DRIVER_ONCE", false);
  for (int i = 1; i < argc; i += 1)
  { std::string arg = argv[i];
   auto next = [&]() -> std::string
   { std::string out;
    if (i + 1 < argc) out = argv[++i];
    return out;
   };
   if (arg == "--api-base-url") config.api_base_url = next();
   else if (arg == "--limit") config.limit = std::max(1, std::stoi(next()));
   else if (arg == "--lookback-days") config.lookback_days = std::max(1, std::stoi(next()));
   else if (arg == "--interval-seconds") config.interval_seconds = std::max(1, std::stoi(next()));
   else if (arg == "--timeout-seconds") config.timeout_seconds = std::max(1, std::stoi(next()));
   else if (arg == "--max-runs") config.max_runs = std::max(0, std::stoi(next()));
   else if (arg == "--trigger-source") config.trigger_source = next();
   else if (arg == "--api-auth-token") config.api_auth_token = next();
   else if (arg == "--once") config.once = true;
   else if (arg == "--force-rematch") config.force_rematch = true;
  }
  return config;
 }

 // #R001: Count selected message ids across the pending-run result rows.
 std::size_t CountSelectedMessages(const json &results)
 { std::size_t total = 0;
  for (const json &row : results)
   if (row.contains("selected_message_ids") && row["selected_message_ids"].is_array())
    total += row["selected_message_ids"].size();
  return total;
 }
}

// #R001: Matchycore traceability implementation coverage.
int main(int argc, char **argv)
{ std::signal(SIGINT, HandleInterrupt);
 Config config = ParseArgs(argc, argv);
 std::string url_error;
 std::string api_base_url = ValidatedApiBaseUrl(config.api_base_url, url_error);
 int exit_code = 0;
 if (!url_error.empty())
 { std::fprintf(stderr, "%s\n", url_error.c_str());
  exit_code = 2;
 }
 else
 { int run_counter = 0;
  bool keep_running = true;
  while (keep_running && !g_interrupted.load())
  { run_counter += 1;
   std::string status_text = "ok";
   std::string failure_text;
   json results = json::array();
   httplib::Client client(api_base_url);
   client.set_connection_timeout(config.timeout_seconds, 0);
   client.set_read_timeout(config.timeout_seconds, 0);
   json payload{{"limit", config.limit}, {"lookback_days", config.lookback_days},
                {"trigger_source", config.trigger_source}, {"force_rematch", config.force_rematch}};
   httplib::Headers headers{{"Authorization", "Bearer " + config.api_auth_token}};
   httplib::Result response =
    client.Post("/v1/matchy/runs/pending", headers, payload.dump(), "application/json");
   if (!response) { status_text = "url_error"; failure_text = httplib::to_string(response.error()); }
   else if (response->status != 200) { status_text = "http_error"; failure_text = std::to_string(response->status); }
   else
   { try
    { json parsed = json::parse(response->body);
     if (parsed.is_object() && parsed.contains("results") && parsed["results"].is_array())
      results = parsed["results"];
    }
    catch (const std::exception &exc) { status_text = "error"; failure_text = exc.what(); }
   }
   std::printf("driver_run=%d status=%s batch_size=%zu selected_messages=%zu trigger_source=%s failure=%s\n",
               run_counter, status_text.c_str(), results.size(), CountSelectedMessages(results),
               config.trigger_source.c_str(), failure_text.c_str());
   std::fflush(stdout);
   bool done_for_once = config.once;
   bool done_for_max_runs = config.max_runs > 0 && run_counter >= config.max_runs;
   if (done_for_once || done_for_max_runs) keep_running = false;
   if (keep_running && !g_interrupted.load()) std::this_thread::sleep_for(std::chrono::seconds(config.interval_seconds));
  }
  if (g_interrupted.load()) std::printf("Matchy driver interrupted; exiting.\n");
 }
 return exit_code;
}
