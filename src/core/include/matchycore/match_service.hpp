#pragma once
#include <memory>
#include <optional>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/ai_ranker.hpp"
#include "matchycore/cldr.hpp"
#include "matchycore/mailcart.hpp"
#include "matchycore/models.hpp"
#include "matchycore/repository.hpp"
#include "matchycore/search.hpp"
#include "matchycore/settings.hpp"

// Port of matchy/service.py + email_move.py: the mixin orchestration becomes one composed class.
namespace matchycore
{ class MatchService
 { public:
  //R310: Construct the full production wiring (Mailcart preflight runs once when enabled).
  explicit MatchService(const Settings &settings);
  // Test/oracle seam: inject the repository profile, Mailcart stub, and AI transport.
  MatchService(const Settings &settings, db::MatchRepository repository,
               std::shared_ptr<mailcart::MailcartApi> mailcart_client,
               std::shared_ptr<ai::AiTransport> ai_transport, cldr::CldrCurrencyMatcher cldr_matcher);
  //R001: Search, enrich, filter, collapse, cache-check, AI pipeline, persist. Throws
  //R001: std::invalid_argument for unknown transaction ids (mapped to HTTP 404).
  nlohmann::json MatchTransaction(const std::string &transaction_id, const std::string &trigger_source = "manual",
                                  bool force_rematch = false, db::Session *external_session = nullptr,
                                  bool record_failure = true);
  //R300 R305: One shared unit of work for the whole batch; any failure rolls everything back.
  std::vector<nlohmann::json> MatchTransactionsAtomic(const std::vector<std::string> &transaction_ids,
                                                      const std::string &trigger_source = "manual",
                                                      bool force_rematch = false);
  //R010 R025 R030: Concurrent pending batch with per-entry fault capture and deterministic order.
  std::vector<nlohmann::json> MatchPendingTransactions(int limit = 100, int lookback_days = 14,
                                                       const std::string &trigger_source = "auto",
                                                       bool force_rematch = false);
  //R045: Human confirm; unknown ids surface as std::invalid_argument (HTTP 404).
  nlohmann::json ConfirmMatch(const std::string &transaction_id, const std::string &email_message_id,
                              const std::optional<std::string> &note = std::nullopt);
  [[nodiscard]] const Settings &settings() const { return settings_; }

  private:
  //R055: Near-duplicate threshold resolver (non-positive disables collapsing).
  [[nodiscard]] int NearDuplicateMaxDistance() const;
  //R060: Optionally move selected emails into the Mailcart matchy folder.
  void MaybeMoveSelectedMessages(const std::vector<std::string> &selected_message_ids,
                                 const std::string &transaction_id, const std::string &source);
  Settings settings_;
  db::MatchRepository repository_;
  std::shared_ptr<mailcart::MailcartApi> mailcart_client_;
  search::SearchEngine search_engine_;
  ai::AiRanker ai_ranker_;
  cldr::CldrCurrencyMatcher cldr_matcher_;
 };
}
