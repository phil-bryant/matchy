// Port of tests/py/test_cldr_cache.py (token parsing + standalone matcher contracts).
#include <catch2/catch_test_macros.hpp>
#include "matchycore/cldr.hpp"

namespace cldr = matchycore::cldr;

namespace
// #R001: Matchycore traceability test coverage.
{ nlohmann::json SamplePayload()
 { nlohmann::json currencies;
  currencies["USD"] = {{"displayName", "US Dollar"}, {"symbol", "$"}, {"symbol-alt-narrow", "$"}};
  currencies["EUR"] = {{"symbol", "\u20ac"}};
  currencies["JPY"] = {{"symbol", "\u00a5"}};
  currencies["XXX"] = {{"symbol", "\u00a4"}};
  currencies["ZAR"] = {{"symbol", "ZAR"}, {"symbol-alt-narrow", "R"}};
  nlohmann::json payload;
  payload["main"]["en"]["numbers"]["currencies"] = currencies;
  return payload;
 }
}

TEST_CASE("parse_currency_tokens extracts codes and clean symbols", "[cldr]")
{ std::set<std::string> tokens = cldr::CldrCurrenciesCache::ParseCurrencyTokens(SamplePayload());
 REQUIRE(tokens.count("USD") == 1);
 REQUIRE(tokens.count("EUR") == 1);
 REQUIRE(tokens.count("$") == 1);
 REQUIRE(tokens.count("\u20ac") == 1);
 REQUIRE(tokens.count("XXX") == 1);
 REQUIRE(tokens.count("\u00a4") == 0); // placeholder symbol excluded
 REQUIRE(tokens.count("R") == 1);      // single-char alnum narrow symbol kept
}

TEST_CASE("matcher requires standalone codes and symbols", "[cldr]")
{ cldr::CldrCurrencyMatcher matcher(cldr::CldrCurrenciesCache::ParseCurrencyTokens(SamplePayload()));
 REQUIRE(matcher.ContainsStandaloneCurrency("Paid 5 USD for the order"));
 REQUIRE(matcher.ContainsStandaloneCurrency("paid 5 usd for the order")); // codes match case-insensitively
 REQUIRE(matcher.ContainsStandaloneCurrency("Total $5.00"));
 REQUIRE(matcher.ContainsStandaloneCurrency("Total \u20ac9,99"));
 REQUIRE_FALSE(matcher.ContainsStandaloneCurrency("xUSDx is not a code"));
 REQUIRE_FALSE(matcher.ContainsStandaloneCurrency("USDC balance")); // trailing alnum blocks the boundary
 REQUIRE_FALSE(matcher.ContainsStandaloneCurrency("no currency in sight"));
}

TEST_CASE("matcher with no tokens never matches", "[cldr]")
{ cldr::CldrCurrencyMatcher matcher(std::set<std::string>{});
 REQUIRE(matcher.tokens().empty());
 REQUIRE_FALSE(matcher.ContainsStandaloneCurrency("Total $5.00"));
}

TEST_CASE("malformed cache content yields empty tokens", "[cldr]")
{ matchycore::Settings settings;
 settings.set_cldr_currencies_cache_path("/nonexistent/dir/cldr-cache.json");
 cldr::CldrCurrenciesCache cache(settings);
 REQUIRE(cache.CurrencyTokens().empty());
}
