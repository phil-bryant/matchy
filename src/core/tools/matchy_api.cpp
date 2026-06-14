// Port of matchy/api.py + 06_run_matchy_api.py: the FastAPI app and its uvicorn launcher
// collapse into one cpp-httplib server preserving the REST contract on 127.0.0.1:8790
// (health, runs, runs/pending, confirm) with Bearer auth, the write-enabled gate, and
// per-endpoint mutation rate limiting so the existing driver and classy stack keep working.
#include <httplib.h>
#include <chrono>
#include <cstdlib>
#include <deque>
#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/cldr.hpp"
#include "matchycore/match_service.hpp"
#include "matchycore/settings.hpp"

namespace
{ using matchycore::MatchService;
 using matchycore::Settings;
 using nlohmann::json;

 // HTTP-shaped failure carried out of handlers to one central response mapper (single return per handler).
 class ApiError : public std::runtime_error
 { public:
// #R001: Matchycore traceability implementation coverage.
  ApiError(int status, std::string detail, bool unauthorized = false)
  : std::runtime_error(detail), status_(status), detail_(std::move(detail)), unauthorized_(unauthorized) {}
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int status() const { return status_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &detail() const { return detail_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] bool unauthorized() const { return unauthorized_; }

  private:
  int status_;
  std::string detail_;
  bool unauthorized_;
 };

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
 std::string ToLower(const std::string &value)
 { std::string out = value;
  for (char &c : out) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  return out;
 }

// #R001: Matchycore traceability implementation coverage.
 bool EnvFlag(const char *name, bool fallback)
 { std::string raw = ToLower(Trim(EnvOr(name, fallback ? "true" : "false")));
  return raw == "true";
 }

// #R001: Matchycore traceability implementation coverage.
 double EnvDouble(const char *name, double fallback)
 { double value = fallback;
  std::string raw = Trim(EnvOr(name, ""));
  if (!raw.empty())
  { try { value = std::stod(raw); }
   catch (const std::exception &) { value = fallback; }
  }
  return value;
 }

// #R001: Matchycore traceability implementation coverage.
 int EnvInt(const char *name, int fallback)
 { int value = fallback;
  std::string raw = Trim(EnvOr(name, ""));
  if (!raw.empty())
  { try { value = std::stoi(raw); }
   catch (const std::exception &) { value = fallback; }
  }
  return value;
 }

 // Constant-time token comparison mirroring secrets.compare_digest.
// #R001: Matchycore traceability implementation coverage.
 bool ConstantTimeEquals(const std::string &left, const std::string &right)
 { unsigned char diff = left.size() == right.size() ? 0 : 1;
  std::size_t count = std::max(left.size(), right.size());
  for (std::size_t i = 0; i < count; i += 1)
  { unsigned char a = i < left.size() ? static_cast<unsigned char>(left[i]) : 0;
   unsigned char b = i < right.size() ? static_cast<unsigned char>(right[i]) : 0;
   diff |= static_cast<unsigned char>(a ^ b);
  }
  return diff == 0;
 }

 // #R001: Per-(path, client) sliding-window throttle for mutating routes.
 class RateLimiter
 { public:
// #R001: Matchycore traceability implementation coverage.
  RateLimiter(double window_seconds, int max_requests)
  : window_seconds_(window_seconds > 0 ? window_seconds : 60.0),
    max_requests_(max_requests >= 1 ? max_requests : 30) {}
// #R001: Matchycore traceability implementation coverage.
  void Enforce(const std::string &path, const std::string &client_host)
  { double now = std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
   std::lock_guard<std::mutex> guard(mutex_);
   std::deque<double> &bucket = buckets_[path + "\n" + client_host];
   while (!bucket.empty() && (now - bucket.front()) > window_seconds_) bucket.pop_front();
   if (static_cast<int>(bucket.size()) >= max_requests_)
    throw ApiError(429, "Rate limit exceeded for this endpoint.");
   bucket.push_back(now);
  }

  private:
  double window_seconds_;
  int max_requests_;
  std::mutex mutex_;
  std::map<std::string, std::deque<double>> buckets_;
 };

 // #R001: Map 06_run_matchy_api.py CLI overrides onto the env vars Settings::FromEnvironment reads.
 void ApplyArgOverrides(int argc, char **argv, std::string &host, int &port, bool &port_guard)
 { for (int i = 1; i < argc; i += 1)
  { std::string arg = argv[i];
   auto next = [&]() -> std::string
   { std::string out;
    if (i + 1 < argc) out = argv[++i];
    return out;
   };
   if (arg == "--host") host = next();
   else if (arg == "--port") port = std::stoi(next());
   else if (arg == "--no-port-guard") port_guard = false;
   else if (arg == "--port-guard") port_guard = true;
   else if (arg == "--mailcart-body-enrichment") setenv("MATCHY_MAILCART_BODY_ENRICHMENT", next().c_str(), 1);
   else if (arg == "--mailcart-body-enrichment-limit")
    setenv("MATCHY_MAILCART_BODY_ENRICHMENT_LIMIT", next().c_str(), 1);
   else if (arg == "--mailcart-body-enrichment-timeout-seconds")
    setenv("MATCHY_MAILCART_BODY_ENRICHMENT_TIMEOUT_SECONDS", next().c_str(), 1);
   else if (arg == "--mailcart-body-enrichment-max-workers")
    setenv("MATCHY_MAILCART_BODY_ENRICHMENT_MAX_WORKERS", next().c_str(), 1);
   else if (arg == "--mailcart-get-message-timeout-seconds")
    setenv("MATCHY_MAILCART_GET_MESSAGE_TIMEOUT_SECONDS", next().c_str(), 1);
   else if (arg == "--pending-max-workers") setenv("MATCHY_PENDING_MAX_WORKERS", next().c_str(), 1);
  }
 }

 // #R001: Reuse an already-running healthy Matchy on the guarded bind target instead of failing.
 bool ExistingMatchyHealthy(const std::string &host, int port)
 { httplib::Client client(host, port);
  client.set_connection_timeout(1, 500000);
  client.set_read_timeout(1, 500000);
  httplib::Result response = client.Get("/health");
  return response && response->status == 200 && response->body.find("\"status\":\"ok\"") != std::string::npos;
 }

// #R001: Matchycore traceability implementation coverage.
 std::string ClientHost(const httplib::Request &request)
 { std::string host = request.remote_addr;
  if (host.empty()) host = "unknown";
  return host;
 }

 // #R001: Resolve the provided token from Bearer or the write-token headers.
 std::string ProvidedToken(const httplib::Request &request)
 { std::string provided;
  if (request.has_header("Authorization"))
  { std::string authorization = request.get_header_value("Authorization");
   if (authorization.rfind("Bearer ", 0) == 0) provided = Trim(authorization.substr(7));
   else provided = Trim(authorization);
  }
  if (provided.empty() && request.has_header("X-Matchy-Write-Token"))
   provided = Trim(request.get_header_value("X-Matchy-Write-Token"));
  if (provided.empty() && request.has_header("X-Teller-Write-Token"))
   provided = Trim(request.get_header_value("X-Teller-Write-Token"));
  return provided;
 }

 // #R001: R005: Validate the explicit-id run body (1..200 non-empty ids, enumerated trigger source).
 void ValidateRunBody(const json &body, std::vector<std::string> &transaction_ids, std::string &trigger_source,
                      bool &force_rematch)
 { bool valid = body.is_object() && body.contains("transaction_ids") && body["transaction_ids"].is_array();
  if (valid) valid = !body["transaction_ids"].empty() && body["transaction_ids"].size() <= 200;
  if (valid)
   for (const json &item : body["transaction_ids"])
    if (!item.is_string() || item.get<std::string>().empty()) valid = false;
  trigger_source = body.value("trigger_source", std::string("manual"));
  if (trigger_source != "auto" && trigger_source != "manual" && trigger_source != "retry") valid = false;
  if (!valid) throw ApiError(422, "Invalid run request body.");
  for (const json &item : body["transaction_ids"]) transaction_ids.push_back(item.get<std::string>());
  force_rematch = body.value("force_rematch", false);
 }

 // #R001: Validate the pending-run body (bounded limit/lookback, enumerated trigger source).
 void ValidatePendingBody(const json &body, int &limit, int &lookback_days, std::string &trigger_source,
                          bool &force_rematch)
 { limit = body.is_object() ? body.value("limit", 100) : 100;
  lookback_days = body.is_object() ? body.value("lookback_days", 14) : 14;
  trigger_source = body.is_object() ? body.value("trigger_source", std::string("auto")) : "auto";
  force_rematch = body.is_object() ? body.value("force_rematch", false) : false;
  bool valid = limit >= 1 && limit <= 500 && lookback_days >= 1 && lookback_days <= 365;
  if (trigger_source != "auto" && trigger_source != "manual" && trigger_source != "retry") valid = false;
  if (!valid) throw ApiError(422, "Invalid pending run request body.");
 }

 // #R001: Validate confirm body (non-empty ids; note excludes the null byte Postgres jsonb rejects).
 void ValidateConfirmBody(const json &body, std::string &transaction_id, std::string &email_message_id,
                          std::optional<std::string> &note)
 { transaction_id = body.is_object() ? body.value("transaction_id", std::string()) : std::string();
  email_message_id = body.is_object() ? body.value("email_message_id", std::string()) : std::string();
  bool valid = !transaction_id.empty() && !email_message_id.empty();
  note = std::nullopt;
  if (body.is_object() && body.contains("note") && !body["note"].is_null())
  { std::string note_value = body["note"].get<std::string>();
   if (note_value.find('\0') != std::string::npos) valid = false;
   note = note_value;
  }
  if (!valid) throw ApiError(422, "Invalid confirm request body.");
 }

 // #R001: Translate a caught exception into the response, matching api.py status mapping.
 void WriteError(httplib::Response &response, const std::exception &error)
 { int status = 500;
  std::string detail = "Internal server error.";
  bool unauthorized = false;
  if (const ApiError *api_error = dynamic_cast<const ApiError *>(&error))
  { status = api_error->status();
   detail = api_error->detail();
   unauthorized = api_error->unauthorized();
  }
  else if (dynamic_cast<const std::invalid_argument *>(&error) != nullptr)
  { status = 404;
   detail = "No transaction matched the supplied transaction_id.";
  }
  if (unauthorized) response.set_header("WWW-Authenticate", "Bearer");
  response.status = status;
  response.set_content(json{{"detail", detail}}.dump(), "application/json");
 }
}

int main(int argc, char **argv)
{ std::string host = EnvOr("MATCHY_API_HOST", "127.0.0.1");
 int port = EnvInt("MATCHY_API_PORT", 8790);
 bool port_guard = EnvFlag("MATCHY_PORT_GUARD", true);
 ApplyArgOverrides(argc, argv, host, port, port_guard);
 int exit_code = 0;
 if (std::string(EnvOr("MATCHY_API_AUTH_TOKEN", "")).empty())
  setenv("MATCHY_API_AUTH_TOKEN", "matchy-local-dev-token", 1);
 bool reuse_existing = port_guard && ExistingMatchyHealthy(host, port);
 if (reuse_existing)
  std::printf("Matchy API already running on %s:%d; reusing existing process.\n", host.c_str(), port);
 else
 { Settings settings = Settings::FromEnvironment();
  if (settings.cldr_currencies_refresh_enabled()) matchycore::cldr::CldrCurrenciesCache(settings).Refresh();
  std::optional<MatchService> service;
  std::mutex service_mutex;
  RateLimiter rate_limiter(EnvDouble("MATCHY_MUTATION_RATE_LIMIT_WINDOW_SECONDS", 60.0),
                           EnvInt("MATCHY_MUTATION_RATE_LIMIT_MAX_REQUESTS", 30));
  // #R001: Lazily build MatchService once; constructor failures surface as HTTP 503.
  auto get_service = [&]() -> MatchService *
  { std::lock_guard<std::mutex> guard(service_mutex);
   if (!service.has_value())
   { try { service.emplace(settings); }
    catch (const std::exception &) {}
   }
   return service.has_value() ? &(*service) : nullptr;
  };
  // #R001: Bearer/write-token auth shared by every mutating route.
  auto require_auth = [&](const httplib::Request &request)
  { std::string configured = settings.matchy_api_auth_token();
   if (configured.empty()) throw ApiError(503, "Matchy API auth token is not configured.");
   std::string provided = ProvidedToken(request);
   if (provided.empty() || !ConstantTimeEquals(provided, configured))
    throw ApiError(401, "Unauthorized", true);
  };
  // #R001: MATCHY_WRITE_ENABLED gate plus the per-endpoint rate limit, run before any mutation.
  auto require_write_and_limit = [&](const httplib::Request &request)
  { if (!settings.write_enabled())
    throw ApiError(503, "Matchy writes are disabled (MATCHY_WRITE_ENABLED=false).");
   rate_limiter.Enforce(request.path, ClientHost(request));
  };
  httplib::Server server;
  // #R001: Health endpoint always returns an ok status payload.
  server.Get("/health", [](const httplib::Request &, httplib::Response &response)
  { response.set_content(json{{"status", "ok"}}.dump(), "application/json");
  });
  // #R001: R490: Match explicit transaction ids atomically; unknown ids map to HTTP 404.
  server.Post("/v1/matchy/runs", [&](const httplib::Request &request, httplib::Response &response)
  { try
   { require_auth(request);
    require_write_and_limit(request);
    std::vector<std::string> transaction_ids;
    std::string trigger_source;
    bool force_rematch = false;
    ValidateRunBody(json::parse(request.body), transaction_ids, trigger_source, force_rematch);
    MatchService *match_service = get_service();
    if (match_service == nullptr) throw ApiError(503, "Match service is unavailable.");
    std::vector<json> rows = match_service->MatchTransactionsAtomic(transaction_ids, trigger_source, force_rematch);
    response.set_content(json{{"results", rows}}.dump(), "application/json");
   }
   catch (const json::exception &) { WriteError(response, ApiError(422, "Invalid run request body.")); }
   catch (const std::exception &error) { WriteError(response, error); }
  });
  // #R001: R495: Discover and batch-match pending unmatched transactions.
  server.Post("/v1/matchy/runs/pending", [&](const httplib::Request &request, httplib::Response &response)
  { try
   { require_auth(request);
    require_write_and_limit(request);
    int limit = 0;
    int lookback_days = 0;
    std::string trigger_source;
    bool force_rematch = false;
    ValidatePendingBody(json::parse(request.body), limit, lookback_days, trigger_source, force_rematch);
    MatchService *match_service = get_service();
    if (match_service == nullptr) throw ApiError(503, "Match service is unavailable.");
    std::vector<json> rows =
     match_service->MatchPendingTransactions(limit, lookback_days, trigger_source, force_rematch);
    response.set_content(json{{"results", rows}}.dump(), "application/json");
   }
   catch (const json::exception &) { WriteError(response, ApiError(422, "Invalid pending run request body.")); }
   catch (const std::exception &error) { WriteError(response, error); }
  });
  // #R001: R500: Human confirm; unknown ids surface as HTTP 404.
  server.Post("/v1/matchy/confirm", [&](const httplib::Request &request, httplib::Response &response)
  { try
   { require_auth(request);
    require_write_and_limit(request);
    std::string transaction_id;
    std::string email_message_id;
    std::optional<std::string> note;
    ValidateConfirmBody(json::parse(request.body), transaction_id, email_message_id, note);
    MatchService *match_service = get_service();
    if (match_service == nullptr) throw ApiError(503, "Match service is unavailable.");
    json result = match_service->ConfirmMatch(transaction_id, email_message_id, note);
    response.set_content(result.dump(), "application/json");
   }
   catch (const json::exception &) { WriteError(response, ApiError(422, "Invalid confirm request body.")); }
   catch (const std::exception &error) { WriteError(response, error); }
  });
  std::printf("Matchy API (C++) listening on %s:%d\n", host.c_str(), port);
  std::fflush(stdout);
  if (!server.listen(host, port))
  { std::fprintf(stderr, "Failed to bind Matchy API on %s:%d\n", host.c_str(), port);
   exit_code = 1;
  }
 }
 return exit_code;
}
