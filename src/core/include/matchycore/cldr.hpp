#pragma once
#include <set>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/settings.hpp"

// Port of matchy/cldr_cache.py (CLDR currency token cache + standalone-currency matcher).
namespace matchycore::cldr
{ class CldrCurrencyMatcher
 { public:
  // #R001: Build matcher state from normalized code/symbol tokens.
  explicit CldrCurrencyMatcher(const std::set<std::string> &tokens);
  // #R001: Match only standalone codes/symbols so substrings like xUSDx do not scope candidates.
  [[nodiscard]] bool ContainsStandaloneCurrency(const std::string &text) const;
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::set<std::string> &tokens() const { return tokens_; }

  private:
  std::set<std::string> tokens_;
  std::vector<std::string> codes_;
  std::vector<std::string> symbols_;
 };

 class CldrCurrenciesCache
 { public:
  explicit CldrCurrenciesCache(const Settings &settings);
  // #R001: R565: Refresh the local cache when the upstream commit changes; failures keep cached state.
  nlohmann::json Refresh();
  [[nodiscard]] CldrCurrencyMatcher CurrencyMatcher() const;
  // #R001: Parse cached tokens, returning an empty set when cache content is missing/invalid.
  [[nodiscard]] std::set<std::string> CurrencyTokens() const;
  // #R001: Extract normalized currency codes and clean symbol variants from the CLDR payload.
  static std::set<std::string> ParseCurrencyTokens(const nlohmann::json &payload);

  private:
  std::string LatestVersion() const;
  std::string DownloadBody() const;
  void WriteCache(const std::string &body, const std::string &version) const;
  static std::string ReadText(const std::string &path);
  std::string cache_path_;
  std::string version_path_;
  int timeout_seconds_;
 };
}
