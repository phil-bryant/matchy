// Port of tests/py/test_search.py (query planning, dedupe, cooldown, error classification).
#include <catch2/catch_test_macros.hpp>
#include <functional>
#include "matchycore/search.hpp"
#include "matchycore/timeutil.hpp"

using matchycore::EmailCandidate;
using matchycore::Settings;
using matchycore::TransactionInput;
using matchycore::mailcart::MailcartApi;
using matchycore::mailcart::MailcartError;
namespace search = matchycore::search;

namespace
{ const matchycore::TimePoint kTxnDate = *matchycore::timeutil::ParseIso8601("2024-06-01T12:00:00+00:00");

 class StubMailcart final : public MailcartApi
 { public:
  std::function<std::vector<EmailCandidate>(const std::string &)> on_search;
  std::vector<std::string> queries;

  std::vector<EmailCandidate> SearchCandidates(const std::string &query, int limit) override
  { (void)limit;
   queries.push_back(query);
   return on_search(query);
  }

  nlohmann::json GetMessage(const std::string &, int) override { return nlohmann::json::object(); }

  bool MoveToMatchy(const std::string &) override { return true; }
 };

 EmailCandidate Candidate(const std::string &id)
 { return EmailCandidate(id, "subject", "preview", kTxnDate);
 }

 TransactionInput Txn()
 { return TransactionInput("t1", "a1", "-10.00", kTxnDate, "Payment to ACME-International ref 0042", "Acme International LLC");
 }
}

TEST_CASE("extract_search_terms filters short numeric and duplicate tokens", "[search]")
{ std::vector<std::string> terms = search::ExtractSearchTerms("Payment to ACME-International 12345 ref 0042",
                                                              "Acme International LLC");
 REQUIRE(terms == std::vector<std::string>{"acme", "international"});
 REQUIRE(search::ExtractSearchTerms("ab 12 x!", "").empty());
 REQUIRE(search::ExtractSearchTerms("4242424242", "").empty());
}

TEST_CASE("scoped queries carry field prefixes and date bounds", "[search]")
{ std::vector<std::string> queries = search::BuildScopedQueries({"acme"}, kTxnDate, {"body"}, true, 45);
 REQUIRE(queries == std::vector<std::string>{"body:acme from:2024-04-17 to:2024-07-16"});
 std::vector<std::string> no_window = search::BuildScopedQueries({"acme"}, kTxnDate, {"subject"}, false, 45);
 REQUIRE(no_window == std::vector<std::string>{"subject:acme"});
 REQUIRE(search::BuildScopedQueries({}, kTxnDate, {"body"}, true, 45).empty());
 REQUIRE(search::DateWindowSuffix(kTxnDate, 0).empty());
}

TEST_CASE("dedupe preserves order drops idless rows and caps", "[search]")
{ EmailCandidate no_id("", "s", "p", kTxnDate);
 std::vector<EmailCandidate> rows{Candidate("a"), no_id, Candidate("b"), Candidate("a"), Candidate("c")};
 std::vector<EmailCandidate> deduped = search::DedupeCandidates(rows, 2);
 REQUIRE(deduped.size() == 2);
 REQUIRE(deduped[0].message_id() == "a");
 REQUIRE(deduped[1].message_id() == "b");
}

TEST_CASE("search early-stops on first successful query", "[search]")
{ auto stub = std::make_shared<StubMailcart>();
 stub->on_search = [](const std::string &) { return std::vector<EmailCandidate>{Candidate("m1")}; };
 search::SearchEngine engine(stub, Settings{});
 std::vector<EmailCandidate> found = engine.SearchCandidates(Txn(), "t1");
 REQUIRE(found.size() == 1);
 REQUIRE(stub->queries.size() == 1);
 REQUIRE(stub->queries[0] == "body:acme from:2024-04-17 to:2024-07-16");
}

TEST_CASE("timeouts skip a query without arming the cooldown", "[search]")
{ auto stub = std::make_shared<StubMailcart>();
 int calls = 0;
 stub->on_search = [&calls](const std::string &) -> std::vector<EmailCandidate>
 { calls += 1;
  if (calls == 1) throw MailcartError(MailcartError::Kind::kTimeout, 0, "slow");
  return {Candidate("m2")};
 };
 search::SearchEngine engine(stub, Settings{});
 std::vector<EmailCandidate> found = engine.SearchCandidates(Txn(), "t1");
 REQUIRE(found.size() == 1);
 REQUIRE_FALSE(engine.InCooldown());
 REQUIRE(calls == 2);
}

TEST_CASE("connection failures arm the cooldown and stop the chain", "[search]")
{ auto stub = std::make_shared<StubMailcart>();
 stub->on_search = [](const std::string &) -> std::vector<EmailCandidate>
 { throw MailcartError(MailcartError::Kind::kConnection, 0, "down");
 };
 search::SearchEngine engine(stub, Settings{});
 REQUIRE(engine.SearchCandidates(Txn(), "t1").empty());
 REQUIRE(engine.InCooldown());
 REQUIRE(stub->queries.size() == 1);
 REQUIRE(engine.SearchCandidates(Txn(), "t1").empty());
 REQUIRE(stub->queries.size() == 1);
}

TEST_CASE("http 5xx arms the cooldown while 4xx propagates", "[search]")
{ auto five = std::make_shared<StubMailcart>();
 five->on_search = [](const std::string &) -> std::vector<EmailCandidate>
 { throw MailcartError(MailcartError::Kind::kHttp, 503, "unavailable");
 };
 search::SearchEngine engine_five(five, Settings{});
 REQUIRE(engine_five.SearchCandidates(Txn(), "t1").empty());
 REQUIRE(engine_five.InCooldown());
 auto four = std::make_shared<StubMailcart>();
 four->on_search = [](const std::string &) -> std::vector<EmailCandidate>
 { throw MailcartError(MailcartError::Kind::kHttp, 400, "bad request");
 };
 search::SearchEngine engine_four(four, Settings{});
 REQUIRE_THROWS_AS(engine_four.SearchCandidates(Txn(), "t1"), MailcartError);
}
