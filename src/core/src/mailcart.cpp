#include "matchycore/mailcart.hpp"
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <thread>
#include <httplib.h>
#include "matchycore/timeutil.hpp"

namespace matchycore::mailcart
{ namespace
 { std::string Lower(const std::string &value)
  { std::string out = value;
   for (char &c : out)
    if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
   return out;
  }

  std::string ExpandUser(const std::string &path)
  { std::string out = path;
   const char *home = std::getenv("HOME");
   if (!path.empty() && path[0] == '~' && home != nullptr) out = std::string(home) + path.substr(1);
   return out;
  }

  std::string UrlEncode(const std::string &value)
  { static const char *hex = "0123456789ABCDEF";
   std::string out;
   for (char c : value)
   { unsigned char uc = static_cast<unsigned char>(c);
    bool safe = (uc >= 'A' && uc <= 'Z') || (uc >= 'a' && uc <= 'z') || (uc >= '0' && uc <= '9')
     || c == '-' || c == '_' || c == '.' || c == '~';
    if (safe) out.push_back(c);
    else
    { out.push_back('%');
     out.push_back(hex[uc >> 4]);
     out.push_back(hex[uc & 0x0f]);
    }
   }
   return out;
  }

  bool IsTimeoutError(httplib::Error error)
  { return error == httplib::Error::ConnectionTimeout || error == httplib::Error::Read
    || error == httplib::Error::Write;
  }

  std::string TrimEnv(const char *name)
  { const char *raw = std::getenv(name);
   std::string value = raw == nullptr ? "" : raw;
   std::size_t begin = value.find_first_not_of(" \t\n\r");
   std::string out;
   if (begin != std::string::npos) out = value.substr(begin, value.find_last_not_of(" \t\n\r") - begin + 1);
   return out;
  }
 }

 MailcartClient::MailcartClient(const Settings &settings)
 { std::string base = settings.mailcart_service_base_url();
  while (!base.empty() && base.back() == '/') base.pop_back();
  ValidateBaseUrl(base);
  base_ = base;
  std::string remainder = base.substr(std::string("https://").size());
  std::size_t colon = remainder.find(':');
  host_ = colon == std::string::npos ? remainder : remainder.substr(0, colon);
  port_ = colon == std::string::npos ? 443 : std::atoi(remainder.substr(colon + 1).c_str());
  token_ = settings.mailcart_service_token();
  message_timeout_seconds_ = settings.mailcart_get_message_timeout_seconds() > 0
   ? settings.mailcart_get_message_timeout_seconds() : 6;
  search_timeout_seconds_ = settings.mailcart_search_timeout_seconds() > 0
   ? settings.mailcart_search_timeout_seconds() : 45;
  startup_healthcheck_timeout_seconds_ = settings.mailcart_startup_healthcheck_timeout_seconds() > 0
   ? settings.mailcart_startup_healthcheck_timeout_seconds() : 2;
  ca_bundle_ = ResolveCaBundle(settings);
 }

 void MailcartClient::ValidateBaseUrl(const std::string &base_url)
 { std::string lowered = Lower(base_url);
  if (lowered.rfind("https://", 0) != 0) throw std::runtime_error("MAILCART_SERVICE_BASE_URL must use https");
  std::string netloc = base_url.substr(std::string("https://").size());
  std::size_t slash = netloc.find('/');
  if (slash != std::string::npos) netloc = netloc.substr(0, slash);
  if (netloc.empty()) throw std::runtime_error("MAILCART_SERVICE_BASE_URL must include host and port");
 }

 std::string MailcartClient::ResolveCaBundle(const Settings &settings)
 { std::string result;
  bool resolved = false;
  std::string explicit_override = settings.mailcart_ca_bundle();
  if (!explicit_override.empty())
  { std::string expanded = ExpandUser(explicit_override);
   if (!std::filesystem::exists(expanded))
    throw std::runtime_error("MATCHY_MAILCART_CA_BUNDLE points to a missing file: " + expanded);
   result = expanded;
   resolved = true;
  }
  std::string requests_ca = TrimEnv("REQUESTS_CA_BUNDLE");
  if (!resolved && !requests_ca.empty())
  { std::string expanded = ExpandUser(requests_ca);
   if (!std::filesystem::exists(expanded))
    throw std::runtime_error("REQUESTS_CA_BUNDLE points to a missing file: " + expanded);
   result = expanded;
   resolved = true;
  }
  std::string ssl_cert = TrimEnv("SSL_CERT_FILE");
  if (!resolved && !ssl_cert.empty())
  { std::string expanded = ExpandUser(ssl_cert);
   if (!std::filesystem::exists(expanded))
    throw std::runtime_error("SSL_CERT_FILE points to a missing file: " + expanded);
   result = expanded;
   resolved = true;
  }
  if (!resolved)
  { std::string mkcert_root = ExpandUser("~/Library/Application Support/mkcert/rootCA.pem");
   if (std::filesystem::exists(mkcert_root))
   { result = mkcert_root;
    resolved = true;
   }
  }
  // The Python reference shells out to `mkcert -CAROOT`; the C++ port honors the equivalent
  // CAROOT env var instead of spawning a subprocess.
  std::string caroot = TrimEnv("CAROOT");
  if (!resolved && !caroot.empty())
  { std::string root = caroot + "/rootCA.pem";
   if (std::filesystem::exists(root)) result = root;
  }
  return result;
 }

 nlohmann::json MailcartClient::RequestJson(const std::string &method, const std::string &path,
                                            const std::string &query_string, const std::string &body,
                                            int timeout_seconds, int *status_out)
 { httplib::SSLClient client(host_, port_);
  if (!ca_bundle_.empty()) client.set_ca_cert_path(ca_bundle_);
  client.enable_server_certificate_verification(true);
  client.set_connection_timeout(timeout_seconds, 0);
  client.set_read_timeout(timeout_seconds, 0);
  client.set_write_timeout(timeout_seconds, 0);
  httplib::Headers headers;
  if (!token_.empty()) headers.emplace("Authorization", "Bearer " + token_);
  std::string target = query_string.empty() ? path : path + "?" + query_string;
  httplib::Result response = method == "POST"
   ? client.Post(target, headers, body, "application/json")
   : client.Get(target, headers);
  if (!response)
  { MailcartError::Kind kind = IsTimeoutError(response.error())
    ? MailcartError::Kind::kTimeout : MailcartError::Kind::kConnection;
   throw MailcartError(kind, 0, "mailcart transport error: " + httplib::to_string(response.error())
    + " base_url=" + base_ + " verify=" + (ca_bundle_.empty() ? "default-cert-store" : ca_bundle_));
  }
  *status_out = response->status;
  nlohmann::json payload = nlohmann::json::object();
  if (!response->body.empty())
  { nlohmann::json parsed = nlohmann::json::parse(response->body, nullptr, false);
   if (!parsed.is_discarded()) payload = parsed;
  }
  return payload;
 }

 void MailcartClient::StartupPreflightHealthcheck()
 { int status = 0;
  try
  { RequestJson("GET", "/health", "", "", startup_healthcheck_timeout_seconds_, &status);
   if (status >= 400)
    throw MailcartError(MailcartError::Kind::kHttp, status, "mailcart /health returned " + std::to_string(status));
  }
  catch (const MailcartError &exc)
  { throw std::runtime_error(std::string("Mailcart startup preflight failed. Check MAILCART_SERVICE_BASE_URL ")
    + "scheme and TLS verify bundle. base_url=" + base_ + " verify="
    + (ca_bundle_.empty() ? "default-cert-store" : ca_bundle_) + " error=" + exc.what());
  }
 }

 std::vector<EmailCandidate> MailcartClient::SearchCandidates(const std::string &query, int limit)
 { int status = 0;
  std::string query_string = "query=" + UrlEncode(query) + "&limit=" + std::to_string(limit);
  nlohmann::json payload = RequestJson("GET", "/v1/messages/search", query_string, "", search_timeout_seconds_, &status);
  if (status >= 400)
   throw MailcartError(MailcartError::Kind::kHttp, status, "mailcart search returned " + std::to_string(status));
  std::vector<EmailCandidate> result;
  if (payload.contains("messages") && payload["messages"].is_array())
  { for (const nlohmann::json &row : payload["messages"])
   { std::string message_id = row.value("message_id", "");
    if (!message_id.empty())
     result.emplace_back(message_id, row.value("subject", ""), row.value("preview", ""),
                         ParseDatetime(row.value("received_at", "")), row.value("sender", ""),
                         row.value("body_text", ""));
   }
  }
  return result;
 }

 nlohmann::json MailcartClient::GetMessage(const std::string &message_id, int timeout_seconds)
 { nlohmann::json result = nlohmann::json::object();
  if (!message_id.empty())
  { int resolved_timeout = timeout_seconds > 0 ? timeout_seconds : message_timeout_seconds_;
   bool done = false;
   int attempt = 0;
   while (!done && attempt < 2)
   { attempt += 1;
    try
    { int status = 0;
     nlohmann::json payload = RequestJson("GET", "/v1/messages/" + message_id, "", "", resolved_timeout, &status);
     if (status == 404) done = true;
     else if ((status == 502 || status == 503 || status == 504) && attempt < 2)
      std::this_thread::sleep_for(std::chrono::milliseconds(150));
     else if (status >= 400)
      throw MailcartError(MailcartError::Kind::kHttp, status, "mailcart get_message returned " + std::to_string(status));
     else
     { if (payload.is_object()) result = payload;
      done = true;
     }
    }
    catch (const MailcartError &exc)
    { if (exc.kind() == MailcartError::Kind::kHttp || attempt >= 2) throw;
     std::this_thread::sleep_for(std::chrono::milliseconds(150));
    }
   }
  }
  return result;
 }

 bool MailcartClient::MoveToMatchy(const std::string &message_id)
 { int status = 0;
  nlohmann::json payload = {{"folder_name", "matchy"}};
  RequestJson("POST", "/v1/messages/" + message_id + "/move", "", payload.dump(), 20, &status);
  return status == 200 || status == 204;
 }

 TimePoint MailcartClient::ParseDatetime(const std::string &value)
 { TimePoint result = std::chrono::time_point_cast<TimePoint::duration>(std::chrono::system_clock::now());
  if (!value.empty())
  { std::optional<TimePoint> parsed = timeutil::ParseIso8601(value);
   if (!parsed.has_value()) throw std::runtime_error("invalid mailcart datetime: " + value);
   result = *parsed;
  }
  return result;
 }
}
