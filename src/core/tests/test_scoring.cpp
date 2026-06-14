// Port of tests/py/test_scoring_core.py (R010/R015/R020/R025/R030/R035/R040-R047/R760/R761 contracts).
#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include <chrono>
#include <cmath>
#include "matchycore/scoring.hpp"

using Catch::Approx;
using matchycore::EmailCandidate;
using matchycore::TimePoint;
using matchycore::TransactionInput;
namespace scoring = matchycore::scoring;

namespace
{ const TimePoint kBaseTime = std::chrono::system_clock::from_time_t(1717243200); // 2024-06-01T12:00:00Z

// #R001: Matchycore traceability test coverage.
 EmailCandidate Candidate(const std::string &subject = "", const std::string &preview = "",
                          const std::string &body_text = "")
 { return EmailCandidate("m1", subject, preview, kBaseTime, "", body_text);
 }

// #R001: Matchycore traceability test coverage.
 TimePoint HoursAfter(double hours)
 { return kBaseTime + std::chrono::duration_cast<TimePoint::duration>(std::chrono::duration<double>(hours * 3600.0));
 }
}

TEST_CASE("normalized_text contracts", "[scoring]")
{ REQUIRE(scoring::NormalizedText("HeLLo") == "hello");
 REQUIRE(scoring::NormalizedText("a,b;c") == "a b c");
 REQUIRE(scoring::NormalizedText("x1 y2") == "x1 y2");
 REQUIRE(scoring::NormalizedText("DoorDash order!") == "doordash order ");
}

TEST_CASE("token_overlap contracts", "[scoring]")
{ REQUIRE(scoring::TokenOverlap("", "") == 0.0);
 REQUIRE(scoring::TokenOverlap("   ", "foo bar") == 0.0);
 REQUIRE(scoring::TokenOverlap("ab ab", "abc abc") == 0.0);
 REQUIRE(scoring::TokenOverlap("xy abc", "abc") == 1.0);
 REQUIRE(scoring::TokenOverlap("abc", "xy abc") == 1.0);
 REQUIRE(scoring::TokenOverlap("foo bar baz", "foo bar qux") == Approx(2.0 / 3.0));
 REQUIRE(scoring::TokenOverlap("alpha beta gamma", "alpha") == Approx(1.0 / 3.0));
 REQUIRE(scoring::TokenOverlap("foo bar", "xy") == 0.0);
}

TEST_CASE("amount_hint_score contracts", "[scoring]")
{ REQUIRE(scoring::AmountHintScore("10.50", Candidate("payment 10.50 posted")) == 1.0);
 REQUIRE(scoring::AmountHintScore("-10.50", Candidate("", "total 10.50 due")) == 1.0);
 REQUIRE(scoring::AmountHintScore("-25.00", Candidate("", "", "charged $25.00 today")) == 1.0);
 REQUIRE(scoring::AmountHintScore("42.00", Candidate("order 42 receipt")) == 1.0);
 REQUIRE(scoring::AmountHintScore("1234.56", Candidate("", "", "Your total is $1,234.56")) == 1.0);
 REQUIRE(scoring::AmountHintScore("42.99", Candidate("order 42 receipt")) == 0.0);
 REQUIRE(scoring::AmountHintScore("99.99", Candidate("newsletter", "unrelated")) == 0.0);
 REQUIRE(scoring::AmountHintScore("1E1000", Candidate("total 10.00 posted")) == 0.0);
}

TEST_CASE("sender_hint_score contracts", "[scoring]")
{ REQUIRE(scoring::SenderHintScore("payment from acme retail", "acme@store.com acme") == 1.0);
 REQUIRE(scoring::SenderHintScore("payment coffee shop", "books@store.com") == 0.0);
 REQUIRE(scoring::SenderHintScore("ab cd ef", "ab gh") == 0.0);
 REQUIRE(scoring::SenderHintScore("", "sender@x.com") == 0.0);
 REQUIRE(scoring::SenderHintScore("merchant payment", "") == 0.0);
 REQUIRE(scoring::SenderHintScore("pay ace billing", "ace@payments.com") == 1.0);
 REQUIRE(scoring::SenderHintScore("pay ace billing", "ace billing team") == 1.0);
}

TEST_CASE("compact_merchant_hint_score contracts", "[scoring]")
{ REQUIRE(scoring::CompactMerchantHintScore("payment widgets", "") == 0.0);
 REQUIRE(scoring::CompactMerchantHintScore("purchase widgets international", "Receipt: WIDGETSINTERNATIONAL-123") == 1.0);
 REQUIRE(scoring::CompactMerchantHintScore("buy alpha", "alphaonly") == 0.0);
 REQUIRE(scoring::CompactMerchantHintScore("ref 12345678", "12345678") == 0.0);
 REQUIRE(scoring::CompactMerchantHintScore("payment coffee", "tea-shop-receipt") == 0.0);
 REQUIRE(scoring::CompactMerchantHintScore("purchase foobar", "foo-bar") == 1.0);
 REQUIRE(scoring::CompactMerchantHintScore("buy widget", "widgetshop") == 1.0);
 REQUIRE(scoring::CompactMerchantHintScore("buy panel", "panelshop") == 0.0);
}

TEST_CASE("time_proximity_score bucket edges", "[scoring]")
{ REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(0)) == 1.0);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(6)) == 1.0);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(6 + 1.0 / 3600.0)) == 0.85);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(24)) == 0.85);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(24 + 1.0 / 3600.0)) == 0.65);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(72)) == 0.65);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(72 + 1.0 / 3600.0)) == 0.3);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(24 * 30)) == 0.3);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(24 * 30 + 1.0 / 3600.0)) == 0.1);
 REQUIRE(scoring::TimeProximityScore(kBaseTime, HoursAfter(-3)) == 1.0);
}

TEST_CASE("relevance_tokens contracts", "[scoring]")
{ REQUIRE(scoring::RelevanceTokens("Coffee, COFFEE!! be xy") == std::vector<std::string>{"coffee", "coffee"});
 REQUIRE(scoring::RelevanceTokens("a bb !! 999") == std::vector<std::string>{"999"});
 REQUIRE(scoring::RelevanceTokens("a bb cc").empty());
}

TEST_CASE("document_frequencies contracts", "[scoring]")
{ std::map<std::string, int> expected{{"coffee", 2}, {"shop", 1}, {"beans", 1}, {"tea", 1}, {"time", 1}};
 REQUIRE(scoring::DocumentFrequencies({"coffee shop", "coffee beans", "tea time tea"}) == expected);
 REQUIRE(scoring::DocumentFrequencies({}).empty());
}

TEST_CASE("inverse_document_frequency contracts", "[scoring]")
{ REQUIRE(scoring::InverseDocumentFrequency(2, 1) == Approx(std::log(2.0)));
 REQUIRE(scoring::InverseDocumentFrequency(10, 1) == Approx(std::log(1.0 + 9.5 / 1.5)));
 REQUIRE(scoring::InverseDocumentFrequency(10, 1) > scoring::InverseDocumentFrequency(10, 5));
}

TEST_CASE("bm25_score contracts", "[scoring]")
{ std::map<std::string, int> coffee_df{{"coffee", 1}};
 REQUIRE(scoring::Bm25Score("coffee", "coffee coffee beans extra terms here", 2, coffee_df, 3.0)
         == Approx(0.749348303).margin(1e-6));
 REQUIRE(scoring::Bm25Score("zzzz", "coffee beans", 2, coffee_df, 3.0) == 0.0);
 REQUIRE(scoring::Bm25Score("coffee", "", 2, coffee_df, 0.0) == 0.0);
 REQUIRE(scoring::Bm25Score("coffee", "coffee beans", 0, coffee_df, 3.0) == 0.0);
 REQUIRE(scoring::Bm25Score("coffee", "coffee coffee", 2, coffee_df, 0.5) == Approx(0.504107040407233).margin(1e-9));
 REQUIRE(scoring::Bm25Score("coffee", "coffee coffee", 2, coffee_df, 0.0) == Approx(0.749348303308049).margin(1e-9));
 REQUIRE(scoring::Bm25Score("coffee", "coffee", 2, coffee_df, 1.0) == Approx(0.6931471805599453).margin(1e-9));
 REQUIRE(scoring::Bm25Score("coffee", "coffee", 1, coffee_df, 1.0) == Approx(0.28768207245178085).margin(1e-9));
 REQUIRE(scoring::Bm25Score("rareword", "rareword beans", 5, {}, 2.0) == Approx(2.4849066497880004).margin(1e-9));
 std::map<std::string, int> both_df{{"coffee", 1}, {"beans", 1}};
 REQUIRE(scoring::Bm25Score("coffee beans", "coffee beans extra", 2, both_df, 3.0)
         == Approx(1.3862943611198906).margin(1e-9));
 REQUIRE(scoring::Bm25Score("coffee", "coffee coffee beans extra terms here", 2, coffee_df, 3.0)
         == Approx(0.749348303308049).margin(1e-12));
}

TEST_CASE("bm25_relevance contracts", "[scoring]")
{ REQUIRE(scoring::Bm25Relevance(4.0, 0.5) == Approx(0.8888888888888888).margin(1e-9));
 REQUIRE(scoring::Bm25Relevance(4.0) == Approx(0.5));
 REQUIRE(scoring::Bm25Relevance(12.0, 4.0) == Approx(0.75));
 REQUIRE(scoring::Bm25Relevance(0.0) == 0.0);
 REQUIRE(scoring::Bm25Relevance(-1.0) == 0.0);
 REQUIRE(scoring::Bm25Relevance(4.0, 0.0) == 0.0);
 REQUIRE(scoring::Bm25Relevance(16.0) == Approx(0.8));
}

TEST_CASE("subset_sum_reachable contracts", "[scoring]")
{ REQUIRE(scoring::SubsetSumReachable({300, 700}, 1000));
 REQUIRE_FALSE(scoring::SubsetSumReachable({300, 800}, 1000));
 REQUIRE_FALSE(scoring::SubsetSumReachable({}, 1000));
 REQUIRE(scoring::SubsetSumReachable({300, 690}, 1000, 10));
 REQUIRE(scoring::SubsetSumReachable({1010}, 1000, 10));
 REQUIRE_FALSE(scoring::SubsetSumReachable({1011}, 1000, 10));
 REQUIRE(scoring::SubsetSumReachable({0, -5, 1000}, 1000));
 REQUIRE_FALSE(scoring::SubsetSumReachable({500}, 0));
 REQUIRE(scoring::SubsetSumReachable({1, 999}, 1000));
 REQUIRE_FALSE(scoring::SubsetSumReachable({999}, 1000));
 REQUIRE_FALSE(scoring::SubsetSumReachable({100}, 99));
 REQUIRE_FALSE(scoring::SubsetSumReachable({100}, 101));
 REQUIRE(scoring::SubsetSumReachable({100}, 100));
}

TEST_CASE("amount_reconciliation_score contracts", "[scoring]")
{ REQUIRE(scoring::AmountReconciliationScore("10.00", Candidate("Item A $3.00", "Item B $7.00", "thanks")) == 1.0);
 EmailCandidate total_only = Candidate("Total $10.00");
 REQUIRE(scoring::AmountHintScore("10.00", total_only) == 1.0);
 REQUIRE(scoring::AmountReconciliationScore("10.00", total_only) == 0.0);
 REQUIRE(scoring::AmountReconciliationScore("10.00", Candidate("$3.00", "$4.00")) == 0.0);
 REQUIRE(scoring::AmountReconciliationScore("10.00", Candidate("newsletter")) == 0.0);
 REQUIRE(scoring::AmountReconciliationScore("0.00", Candidate("$3.00", "$4.00")) == 0.0);
 REQUIRE(scoring::AmountReconciliationScore("10.00", Candidate("rounding $0.01", "charge $9.99")) == 1.0);
 REQUIRE(scoring::AmountReconciliationScore("1E1000", Candidate("Item A $3.00", "Item B $7.00")) == 0.0);
}

TEST_CASE("decimal_to_cents contracts", "[scoring]")
{ REQUIRE(scoring::DecimalToCents("0.005") == 1);
 REQUIRE(scoring::DecimalToCents("0.015") == 2);
 REQUIRE(scoring::DecimalToCents("1.00") == 100);
 REQUIRE(scoring::DecimalToCents("3.50") == 350);
 REQUIRE_FALSE(scoring::DecimalToCents("1E1000").has_value());
 REQUIRE_FALSE(scoring::DecimalToCents("garbage").has_value());
}

TEST_CASE("extract_money_cents contracts", "[scoring]")
{ std::set<long long> extracted = scoring::ExtractMoneyCents("total $1,234.56, adjustment -7.00, tip 0.99, invalid 12.345");
 REQUIRE(extracted.count(123456) == 1);
 REQUIRE(extracted.count(700) == 1);
 REQUIRE(extracted.count(99) == 1);
 REQUIRE(extracted.count(1234) == 0);
}

TEST_CASE("bm25 and reconciliation blend inputs stay bounded", "[scoring]")
{ EmailCandidate candidate = Candidate("Item A $3.00", "Item B $7.00", "coffee receipt");
 double bm25_raw = scoring::Bm25Score("coffee", "coffee receipt", 1, {{"coffee", 1}}, 2.0);
 double bm25_value = scoring::Bm25Relevance(bm25_raw);
 double reconciliation = scoring::AmountReconciliationScore("10.00", candidate);
 REQUIRE(bm25_value >= 0.0);
 REQUIRE(bm25_value <= 1.0);
 REQUIRE((reconciliation == 0.0 || reconciliation == 1.0));
}

TEST_CASE("rank_candidates sorts descending with stable reason keys", "[scoring]")
{ TransactionInput txn("t1", "a1", "-10.50", kBaseTime, "coffee shop purchase", "Blue Bottle Coffee");
 EmailCandidate strong("m-strong", "Blue Bottle Coffee receipt 10.50", "coffee shop order", kBaseTime, "receipts@bluebottle.com", "total 10.50 coffee");
 EmailCandidate weak("m-weak", "gardening newsletter", "weekly digest", HoursAfter(24 * 60), "news@garden.com", "plants and soil");
 std::vector<matchycore::RankedCandidate> ranked = scoring::RankCandidates(txn, {weak, strong}, {});
 REQUIRE(ranked.size() == 2);
 REQUIRE(ranked[0].candidate().message_id() == "m-strong");
 REQUIRE(ranked[0].score() >= ranked[1].score());
 REQUIRE(ranked[0].reasons().contains("merchant_overlap"));
 REQUIRE(ranked[0].reasons().contains("bm25_relevance"));
 REQUIRE(ranked[0].reasons().contains("amount_reconciliation"));
 REQUIRE(ranked[0].reasons()["unmatched_email_priority"] == true);
 REQUIRE(ranked[0].score() <= 1.0);
}

TEST_CASE("rank_candidates unmatched bonus prefers unseen messages", "[scoring]")
{ TransactionInput txn("t1", "a1", "-10.50", kBaseTime, "coffee", "coffee");
 EmailCandidate a("m-a", "coffee", "", kBaseTime, "", "");
 EmailCandidate b("m-b", "coffee", "", kBaseTime, "", "");
 std::vector<matchycore::RankedCandidate> ranked = scoring::RankCandidates(txn, {a, b}, {"m-a"});
 REQUIRE(ranked[0].candidate().message_id() == "m-b");
 REQUIRE(ranked[0].reasons()["unmatched_email_priority"] == true);
 REQUIRE(ranked[1].reasons()["unmatched_email_priority"] == false);
}
