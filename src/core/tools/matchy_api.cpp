// Port of matchy/api.py + 06_run_matchy_api.py: the FastAPI app and its uvicorn launcher
// collapse into one cpp-httplib server preserving the REST contract on 127.0.0.1:8790
// (health, runs, runs/pending, confirm) with Bearer auth, the write-enabled gate, and
// per-endpoint mutation rate limiting so the existing driver and classy stack keep working.
#include <httplib.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/api_contract.hpp"
#include "matchycore/cldr.hpp"
#include "matchycore/match_service.hpp"
#include "matchycore/settings.hpp"

namespace
{ using matchycore::MatchService;
 using matchycore::Settings;
 using matchycore::apicontract::ApiError;
 using matchycore::apicontract::ErrorOutcome;
 using matchycore::apicontract::ValidateConfirmBody;
 using matchycore::apicontract::ValidatePendingBody;
 using matchycore::apicontract::ValidateRunBody;
 using nlohmann::json;

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
   else if (arg == "--profile")
   { setenv("MATCHY_STARTUP_LOG", "true", 1);
    setenv("MATCHY_RUNTIME_PROFILE", "true", 1);
   }
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

 // #R001: Detect whether a TCP listener already occupies the guarded bind target.
 bool PortInUse(const std::string &host, int port)
 { bool in_use = false;
  int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd >= 0)
  { sockaddr_in addr{};
   addr.sin_family = AF_INET;
   addr.sin_port = htons(static_cast<std::uint16_t>(port));
   std::string ip = host == "localhost" ? std::string("127.0.0.1") : host;
   if (::inet_pton(AF_INET, ip.c_str(), &addr.sin_addr) == 1)
    if (::connect(fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 0) in_use = true;
   ::close(fd);
  }
  return in_use;
 }

 // #R001: Minimal OpenAPI 3.0 document describing the four production routes (docs parity with create_app()).
 json OpenApiSpec()
 { json post = json{{"responses", {{"200", {{"description", "Match results."}}}}}};
  return json{
   {"openapi", "3.0.2"},
   {"info", {{"title", "matchy"}, {"version", "0.1.0"}}},
   {"paths", {
    {"/health", {{"get", {{"responses", {{"200", {{"description", "Service is healthy."}}}}}}}}},
    {"/v1/matchy/runs", {{"post", post}}},
    {"/v1/matchy/runs/pending", {{"post", post}}},
    {"/v1/matchy/confirm", {{"post", post}}}}}};
 }

 // #R001: Swagger/Redoc CDN HTML mirroring FastAPI's docs pages, pointed at /openapi.json.
 std::string DocsHtml(const std::string &title, bool redoc)
 { std::string head = "<!DOCTYPE html><html><head><title>" + title + "</title></head><body>";
  std::string body = redoc
   ? "<redoc spec-url='/openapi.json'></redoc>"
     "<script src='https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js'></script>"
   : "<div id='swagger-ui'></div>"
     "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui.css'>"
     "<script src='https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-bundle.js'></script>"
     "<script>window.onload=function(){SwaggerUIBundle({url:'/openapi.json',dom_id:'#swagger-ui'});};</script>";
  return head + body + "</body></html>";
 }

 // #R001: Translate a caught exception into the response, matching api.py status mapping.
 void WriteError(httplib::Response &response, const std::exception &error)
 { ErrorOutcome outcome = matchycore::apicontract::MapError(error);
  if (outcome.unauthorized()) response.set_header("WWW-Authenticate", "Bearer");
  response.status = outcome.status();
  response.set_content(outcome.body().dump(), "application/json");
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
 bool port_in_use = port_guard && PortInUse(host, port);
 bool reuse_existing = port_in_use && ExistingMatchyHealthy(host, port);
 bool port_conflict = port_in_use && !reuse_existing;
 if (port_conflict)
 { std::fprintf(stderr, "Port %d is already in use by another process.\n", port);
  exit_code = 1;
 }
 else if (reuse_existing)
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
  // #R001: Optional OpenAPI/docs surfaces, gated by MATCHY_ENABLE_API_DOCS to mirror create_app().
  if (EnvFlag("MATCHY_ENABLE_API_DOCS", false))
  { server.Get("/openapi.json", [](const httplib::Request &, httplib::Response &response)
   { response.set_content(OpenApiSpec().dump(), "application/json");
   });
   server.Get("/docs", [](const httplib::Request &, httplib::Response &response)
   { response.set_content(DocsHtml("matchy - Swagger UI", false), "text/html");
   });
   server.Get("/redoc", [](const httplib::Request &, httplib::Response &response)
   { response.set_content(DocsHtml("matchy - ReDoc", true), "text/html");
   });
  }
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
    json result;
    try { result = match_service->ConfirmMatch(transaction_id, email_message_id, note); }
    catch (const std::invalid_argument &)
    { throw ApiError(404, "Unknown transaction or email message for confirmation."); }
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
