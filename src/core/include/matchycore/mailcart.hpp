#pragma once
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/models.hpp"
#include "matchycore/settings.hpp"

// Port of matchy/mailcart_client.py (HTTPS-only Mailcart client with mkcert-aware trust resolution).
namespace matchycore::mailcart
{ class MailcartError : public std::runtime_error
 { public:
  enum class Kind { kTimeout, kConnection, kHttp };
  MailcartError(Kind kind, int status, const std::string &message)
  : std::runtime_error(message), kind_(kind), status_(status) {}
  [[nodiscard]] Kind kind() const { return kind_; }
  [[nodiscard]] int status() const { return status_; }

  private:
  Kind kind_;
  int status_;
 };

 // Interface so the service/search/enrichment layers can be tested against stubs.
 class MailcartApi
 { public:
  virtual ~MailcartApi() = default;
  //R005: Convert search payload rows into EmailCandidate values, dropping rows without message ids.
  virtual std::vector<EmailCandidate> SearchCandidates(const std::string &query, int limit) = 0;
  //R010: Fetch one message envelope; empty object on 404 or empty id. timeout_seconds <= 0 uses the default.
  virtual nlohmann::json GetMessage(const std::string &message_id, int timeout_seconds) = 0;
  //R644: Move a message into the matchy folder; true only for HTTP 200/204.
  virtual bool MoveToMatchy(const std::string &message_id) = 0;
 };

 class MailcartClient final : public MailcartApi
 { public:
  explicit MailcartClient(const Settings &settings);
  //R050: Probe /health with runtime transport policy so startup catches misconfiguration early.
  void StartupPreflightHealthcheck();
  std::vector<EmailCandidate> SearchCandidates(const std::string &query, int limit) override;
  nlohmann::json GetMessage(const std::string &message_id, int timeout_seconds) override;
  bool MoveToMatchy(const std::string &message_id) override;
  //R640: Enforce an HTTPS base URL with a non-empty host component; throws std::runtime_error.
  static void ValidateBaseUrl(const std::string &base_url);
  //R045: Resolve the TLS trust bundle (explicit override, env bundles, mkcert root, else system default "").
  static std::string ResolveCaBundle(const Settings &settings);
  //R645: Parse Mailcart datetimes, defaulting blanks to now-UTC and attaching UTC when offset is missing.
  static TimePoint ParseDatetime(const std::string &value);

  private:
  nlohmann::json RequestJson(const std::string &method, const std::string &path, const std::string &query_string,
                             const std::string &body, int timeout_seconds, int *status_out);
  std::string base_;
  std::string host_;
  int port_;
  std::string token_;
  std::string ca_bundle_;
  int message_timeout_seconds_;
  int search_timeout_seconds_;
  int startup_healthcheck_timeout_seconds_;
 };
}
