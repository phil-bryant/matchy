// Port of tests/py/test_enrichment.py (body enrichment + CLDR currency scoping).
#include <catch2/catch_test_macros.hpp>
#include <mutex>
#include "matchycore/enrichment.hpp"
#include "matchycore/timeutil.hpp"

using matchycore::EmailCandidate;
using matchycore::Settings;
using matchycore::mailcart::MailcartApi;
namespace enrichment = matchycore::enrichment;
namespace cldr = matchycore::cldr;

namespace
{ const matchycore::TimePoint kTime = *matchycore::timeutil::ParseIso8601("2024-06-01T12:00:00+00:00");

 class StubMailcart final : public MailcartApi
 { public:
  std::map<std::string, nlohmann::json> payloads;
  std::vector<std::string> fetched;
  std::mutex mutex;

// #R001: Matchycore traceability test coverage.
  std::vector<EmailCandidate> SearchCandidates(const std::string &, int) override { return {}; }

// #R001: Matchycore traceability test coverage.
  nlohmann::json GetMessage(const std::string &message_id, int) override
  { std::lock_guard<std::mutex> lock(mutex);
   fetched.push_back(message_id);
   auto found = payloads.find(message_id);
   return found == payloads.end() ? nlohmann::json::object() : found->second;
  }

// #R001: Matchycore traceability test coverage.
  bool MoveToMatchy(const std::string &) override { return true; }
 };
}

TEST_CASE("enrichment replaces bodies with full mailcart message body", "[enrichment]")
{ auto stub = std::make_shared<StubMailcart>();
 stub->payloads["m1"] = {{"text_body", "Order total $12.34 thanks"}};
 Settings settings;
 std::vector<EmailCandidate> candidates{EmailCandidate("m1", "Receipt", "preview", kTime, "shop@x.com", "")};
 std::vector<EmailCandidate> enriched = enrichment::EnrichCandidateBodies(stub, settings, candidates, "t1");
 REQUIRE(enriched.size() == 1);
 REQUIRE(enriched[0].body_text() == "Order total $12.34 thanks");
 REQUIRE(enriched[0].subject() == "Receipt");
}

TEST_CASE("enrichment fetches duplicate message ids only once", "[enrichment]")
{ auto stub = std::make_shared<StubMailcart>();
 stub->payloads["m1"] = {{"text_body", "body"}};
 Settings settings;
 std::vector<EmailCandidate> candidates{EmailCandidate("m1", "a", "p", kTime), EmailCandidate("m1", "b", "p", kTime)};
 enrichment::EnrichCandidateBodies(stub, settings, candidates, "t1");
 REQUIRE(stub->fetched.size() == 1);
}

TEST_CASE("enrichment is skipped when the feature flag is disabled", "[enrichment]")
{ auto stub = std::make_shared<StubMailcart>();
 Settings settings;
 settings.set_mailcart_body_enrichment_enabled(false);
 std::vector<EmailCandidate> candidates{EmailCandidate("m1", "a", "p", kTime, "", "original")};
 std::vector<EmailCandidate> result = enrichment::EnrichCandidateBodies(stub, settings, candidates, "t1");
 REQUIRE(result[0].body_text() == "original");
 REQUIRE(stub->fetched.empty());
}

TEST_CASE("enrichment body text prefers text_body then html_body then body_text", "[enrichment]")
{ REQUIRE(enrichment::EnrichmentBodyText({{"text_body", " plain "}, {"html_body", "<b>h</b>"}}) == "plain");
 REQUIRE(enrichment::EnrichmentBodyText({{"text_body", ""}, {"html_body", "<b>h</b>"}}) == "<b>h</b>");
 REQUIRE(enrichment::EnrichmentBodyText({{"body_text", "fallback"}}) == "fallback");
 REQUIRE(enrichment::EnrichmentBodyText(nlohmann::json::object()).empty());
}

TEST_CASE("per-candidate failures fall back to the original candidate", "[enrichment]")
{ auto stub = std::make_shared<StubMailcart>();
 Settings settings;
 std::vector<EmailCandidate> candidates{EmailCandidate("missing", "a", "p", kTime, "", "kept")};
 std::vector<EmailCandidate> result = enrichment::EnrichCandidateBodies(stub, settings, candidates, "t1");
 REQUIRE(result[0].body_text() == "kept");
}

TEST_CASE("currency filter scopes candidates to standalone CLDR tokens", "[enrichment]")
{ cldr::CldrCurrencyMatcher matcher(std::set<std::string>{"USD", "$"});
 std::vector<EmailCandidate> candidates{
  EmailCandidate("dollar", "Total $5.00", "", kTime),
  EmailCandidate("code", "paid 5 USD today", "", kTime),
  EmailCandidate("embedded", "xUSDx token", "", kTime),
  EmailCandidate("none", "no currency here", "", kTime)};
 std::vector<EmailCandidate> filtered = enrichment::FilterCurrencyCandidates(matcher, candidates);
 REQUIRE(filtered.size() == 2);
 REQUIRE(filtered[0].message_id() == "dollar");
 REQUIRE(filtered[1].message_id() == "code");
}

TEST_CASE("empty matcher leaves candidates unfiltered", "[enrichment]")
{ cldr::CldrCurrencyMatcher matcher(std::set<std::string>{});
 std::vector<EmailCandidate> candidates{EmailCandidate("any", "no currency", "", kTime)};
 REQUIRE(enrichment::FilterCurrencyCandidates(matcher, candidates).size() == 1);
}
