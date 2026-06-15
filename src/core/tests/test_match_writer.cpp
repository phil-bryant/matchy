// Focused unit coverage for the matchycore match_writer persistence helpers (active-match lifecycle:
// HasActiveMatch, DeactivateActiveMatch, InsertHumanConfirmedMatch) over the SQLCipher mirror schema.
#include <catch2/catch_test_macros.hpp>
#include <string>
#include <vector>
#include "fixture.hpp"
#include "matchycore/models.hpp"
#include "matchycore/timeutil.hpp"

using matchycore::AiSelection;
using matchycore::EmailCandidate;
using matchycore::RankedCandidate;
namespace db = matchycore::db;

namespace
{ const matchycore::TimePoint kWhen = *matchycore::timeutil::ParseIso8601("2024-06-01T15:00:00+00:00");

// #R001: Build a ranked candidate fixture with a stable received-at and reasons map.
 RankedCandidate Ranked(const std::string &id, double score)
 { return RankedCandidate(EmailCandidate(id, "Receipt " + id, "preview", kWhen, "shop@x.com", "body"), score,
                          {{"merchant_overlap", 0.5}});
 }
}

TEST_CASE("HasActiveMatch tracks the persisted active selection", "[match_writer]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 long long run_id = repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
 AiSelection selection({"m1"}, 0.95, false, "match", "anthropic", "model");
 repository.PersistAiResult(*session, "txn-1", run_id, {Ranked("m1", 0.95)}, selection, 0.90);
 REQUIRE(repository.HasActiveMatch(*session, "m1"));
 repository.DeactivateActiveMatch(*session, "txn-1");
 REQUIRE_FALSE(repository.HasActiveMatch(*session, "m1"));
 session->Complete();
}

TEST_CASE("InsertHumanConfirmedMatch records a human-confirmed active row", "[match_writer]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 long long run_id = repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
 AiSelection selection({"m1"}, 0.95, false, "match", "anthropic", "model");
 repository.PersistAiResult(*session, "txn-1", run_id, {Ranked("m1", 0.95)}, selection, 0.90);
 repository.DeactivateActiveMatch(*session, "txn-1");
 long long match_id = repository.InsertHumanConfirmedMatch(*session, "txn-1", "m2", std::string("manual override"));
 REQUIRE(match_id > 0);
 auto active = repository.ReadActiveMatchSummary(*session, "txn-1");
 REQUIRE(active.has_value());
 REQUIRE((*active)["state"] == "human_confirmed_ai_match");
 REQUIRE((*active)["email_message_id"] == "m2");
 REQUIRE((*active)["selected_by"] == "human");
 session->Complete();
}
