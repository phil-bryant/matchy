#pragma once
#include <chrono>
#include <memory>
#include <string>
#include <vector>
#include "matchycore/mailcart.hpp"
#include "matchycore/models.hpp"
#include "matchycore/settings.hpp"

// Port of matchy/search.py (scoped retrieval fallback chain with transient-failure cooldown).
namespace matchycore::search
{ // #R001: Deterministic search terms from counterparty/description text (short, numeric, duplicate tokens filtered).
 std::vector<std::string> ExtractSearchTerms(const std::string &description, const std::string &counterparty_name,
                                             int max_terms = 2);

 // #R001: Inclusive from/to date window suffix around the transaction date; empty when window_days <= 0.
 std::string DateWindowSuffix(TimePoint txn_date, int window_days);

 // #R001: Scoped Mailcart queries per term/field combination, optionally suffixed with the date window.
 std::vector<std::string> BuildScopedQueries(const std::vector<std::string> &terms, TimePoint txn_date,
                                             const std::vector<std::string> &fields, bool include_date_window,
                                             int window_days);

 // #R001: De-duplicate by message_id preserving order, dropping id-less rows, capped at limit.
 std::vector<EmailCandidate> DedupeCandidates(const std::vector<EmailCandidate> &rows, std::size_t limit);

 class SearchEngine
 { public:
  SearchEngine(std::shared_ptr<mailcart::MailcartApi> client, const Settings &settings);
  // #R001: Execute the fallback chain (body+date -> subject+date -> body -> empty) with early stop.
  std::vector<EmailCandidate> SearchCandidates(const TransactionInput &txn, const std::string &transaction_id);
  // #R001: True while the transient-failure cooldown window is active.
  [[nodiscard]] bool InCooldown() const;

  private:
  std::vector<EmailCandidate> SearchMailcart(const std::string &query, const std::string &transaction_id, int limit);
  void MarkTemporarilyUnavailable();
  std::shared_ptr<mailcart::MailcartApi> client_;
  int window_days_;
  int cooldown_seconds_;
  std::chrono::steady_clock::time_point unavailable_until_{};
 };
}
