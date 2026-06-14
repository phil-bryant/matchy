// End-to-end MatchService orchestration over the SQLCipher fixture with stubbed Mailcart + AI.
#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include "fixture.hpp"
#include "matchycore/match_service.hpp"
#include "matchycore/timeutil.hpp"

using Catch::Approx;
using matchycore::EmailCandidate;
using matchycore::MatchService;
using matchycore::Settings;
namespace cldr = matchycore::cldr;
namespace mailcart = matchycore::mailcart;

namespace
{ const matchycore::TimePoint kReceived = *matchycore::timeutil::ParseIso8601("2024-06-01T15:00:00+00:00");

 class StubMailcart final : public mailcart::MailcartApi
 { public:
  std::vector<EmailCandidate> results;
  std::vector<std::string> moved;

// #R001: Matchycore traceability test coverage.
  std::vector<EmailCandidate> SearchCandidates(const std::string &, int) override { return results; }

// #R001: Matchycore traceability test coverage.
  nlohmann::json GetMessage(const std::string &, int) override { return nlohmann::json::object(); }

// #R001: Matchycore traceability test coverage.
  bool MoveToMatchy(const std::string &message_id) override
  { moved.push_back(message_id);
   return true;
  }
 };

 class StubTransport final : public matchycore::ai::AiTransport
 { public:
// #R001: Matchycore traceability test coverage.
  std::string CreateAnthropicMessage(const std::string &, const std::string &) override { return "{}"; }

// #R001: Matchycore traceability test coverage.
  std::string CreateOpenAiResponse(const std::string &, const std::string &) override { return "{}"; }
 };

// #R001: Matchycore traceability test coverage.
 MatchService BuildService(const matchycore::testfx::Fixture &fixture, std::shared_ptr<StubMailcart> stub,
                           Settings settings = Settings{})
 { settings.set_mailcart_body_enrichment_enabled(false);
  return MatchService(settings, fixture.Repository(settings.write_enabled()), stub,
                      std::make_shared<StubTransport>(), cldr::CldrCurrencyMatcher(std::set<std::string>{}));
 }
}

TEST_CASE("match_transaction persists deterministic selection end-to-end", "[service]")
{ matchycore::testfx::Fixture fixture;
 auto stub = std::make_shared<StubMailcart>();
 stub->results = {
  EmailCandidate("m-strong", "Blue Bottle Coffee receipt 10.50", "coffee order", kReceived,
                 "receipts@bluebottle.com", "total 10.50 blue bottle coffee"),
  EmailCandidate("m-weak", "gardening newsletter", "digest", kReceived, "news@garden.com", "plants")};
 MatchService service = BuildService(fixture, stub);
 nlohmann::json result = service.MatchTransaction("txn-1");
 REQUIRE(result["transaction_id"] == "txn-1");
 REQUIRE(result["run_id"] == 1);
 REQUIRE(result["skipped"] == false);
 REQUIRE(result["candidate_count"] == 2);
 REQUIRE(result["selected_message_ids"].size() >= 1);
 REQUIRE(result["selected_message_ids"][0] == "m-strong");
 auto repository = fixture.Repository();
 auto session = repository.OpenSession();
 auto summary = repository.ReadLastRunSummary(*session, "txn-1");
 REQUIRE(summary.has_value());
 REQUIRE((*summary)["candidate_cache_rows"].size() == 2);
 auto active = repository.ReadActiveMatchSummary(*session, "txn-1");
 REQUIRE(active.has_value());
 REQUIRE((*active)["email_message_id"] == "m-strong");
 session->Complete();
}

TEST_CASE("unknown transaction raises invalid_argument", "[service]")
{ matchycore::testfx::Fixture fixture;
 MatchService service = BuildService(fixture, std::make_shared<StubMailcart>());
 REQUIRE_THROWS_AS(service.MatchTransaction("missing-txn"), std::invalid_argument);
}

TEST_CASE("atomic batch matches all ids in one unit of work", "[service]")
{ matchycore::testfx::Fixture fixture;
 auto stub = std::make_shared<StubMailcart>();
 MatchService service = BuildService(fixture, stub);
 std::vector<nlohmann::json> rows = service.MatchTransactionsAtomic({"txn-1", "txn-2"});
 REQUIRE(rows.size() == 2);
 REQUIRE(rows[0]["transaction_id"] == "txn-1");
 REQUIRE(rows[1]["transaction_id"] == "txn-2");
 REQUIRE(rows[0]["candidate_count"] == 0); // stub returned no candidates
 REQUIRE(rows[0]["uncertain"] == true);
}

TEST_CASE("pending batch captures per-entry errors without aborting", "[service]")
{ matchycore::testfx::Fixture fixture;
 auto stub = std::make_shared<StubMailcart>();
 MatchService service = BuildService(fixture, stub);
 std::vector<nlohmann::json> rows = service.MatchPendingTransactions(100, 14);
 REQUIRE(rows.size() == 2);
 for (const nlohmann::json &row : rows)
 { REQUIRE(row.contains("transaction_id"));
  REQUIRE(row["skipped"] == false);
 }
}

TEST_CASE("confirm_match inserts human row and unknown ids map to domain error", "[service]")
{ matchycore::testfx::Fixture fixture;
 auto stub = std::make_shared<StubMailcart>();
 Settings settings;
 settings.set_email_move_enabled(true);
 MatchService service = BuildService(fixture, stub, settings);
 nlohmann::json confirmed = service.ConfirmMatch("txn-1", "m-confirmed", std::string("ok"));
 REQUIRE(confirmed["status"] == "confirmed");
 REQUIRE(confirmed["match_id"].get<long long>() > 0);
 REQUIRE(stub->moved == std::vector<std::string>{"m-confirmed"});
 REQUIRE_THROWS_AS(service.ConfirmMatch("missing-txn", "m-x", std::nullopt), std::invalid_argument);
}

TEST_CASE("email move stays disabled by default", "[service]")
{ matchycore::testfx::Fixture fixture;
 auto stub = std::make_shared<StubMailcart>();
 MatchService service = BuildService(fixture, stub);
 service.ConfirmMatch("txn-1", "m-quiet", std::nullopt);
 REQUIRE(stub->moved.empty());
}
