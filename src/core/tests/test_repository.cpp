// Port of tests/py/test_repository.py + test_match_writer.py over the SQLCipher mirror schema.
#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include "fixture.hpp"
#include "matchycore/caching.hpp"
#include "matchycore/scoring.hpp"
#include "matchycore/timeutil.hpp"

using Catch::Approx;
using matchycore::AiSelection;
using matchycore::EmailCandidate;
using matchycore::RankedCandidate;
namespace db = matchycore::db;
namespace caching = matchycore::caching;

namespace
{ const matchycore::TimePoint kReceived = *matchycore::timeutil::ParseIso8601("2024-06-01T15:00:00+00:00");

 RankedCandidate Ranked(const std::string &id, double score)
 { return RankedCandidate(EmailCandidate(id, "Receipt " + id, "preview", kReceived, "shop@x.com", "body"), score,
                          {{"merchant_overlap", 0.5}, {"unmatched_email_priority", true}});
 }
}

TEST_CASE("sql_for_target rewrites owned schemas for sqlite only", "[repository]")
{ std::string sql = "SELECT * FROM matchy.transaction_email_match JOIN teller.transaction tt";
 REQUIRE(db::SqlForTarget(sql, false) == sql);
 std::string rewritten = db::SqlForTarget(sql, true);
 REQUIRE(rewritten.find("teller.matchy_transaction_email_match") != std::string::npos);
 REQUIRE(rewritten.find("teller.\"transaction\" tt") != std::string::npos);
 REQUIRE(db::JsonbParam("x", true) == ":x");
 REQUIRE(db::JsonbParam("x", false) == "CAST(:x AS jsonb)");
}

TEST_CASE("as_datetime parses both backend text shapes", "[repository]")
{ auto naive = db::AsDatetime(tellercore::db::Value(std::string("2024-06-01 12:00:00")));
 REQUIRE(naive.has_value());
 REQUIRE(naive->Iso() == "2024-06-01T12:00:00");
 auto date_only = db::AsDatetime(tellercore::db::Value(std::string("2024-06-01")));
 REQUIRE(date_only.has_value());
 REQUIRE(date_only->Iso() == "2024-06-01T00:00:00");
 auto tz = db::AsDatetime(tellercore::db::Value(std::string("2024-06-01 12:00:00+00")));
 REQUIRE(tz.has_value());
 REQUIRE(tz->Iso() == "2024-06-01T12:00:00+00:00");
 REQUIRE_FALSE(db::AsDatetime(tellercore::db::Value(std::monostate{})).has_value());
 REQUIRE_FALSE(db::AsDatetime(tellercore::db::Value(std::string("   "))).has_value());
}

TEST_CASE("load_transaction normalizes sqlite cents and counterparty", "[repository]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 auto txn = repository.LoadTransaction(*session, "txn-1");
 REQUIRE(txn.has_value());
 REQUIRE(txn->amount() == "-10.5"); // Decimal(-1050)/100 renders without a trailing zero
 REQUIRE(txn->counterparty_name() == "Blue Bottle Coffee");
 REQUIRE(matchycore::timeutil::FormatIsoUtc(txn->date()) == "2024-06-01T00:00:00+00:00");
 auto missing = repository.LoadTransaction(*session, "nope");
 REQUIRE_FALSE(missing.has_value());
 session->Complete();
}

TEST_CASE("create_run insert_candidates and summaries round-trip", "[repository]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 long long run_id = repository.CreateRun(*session, "txn-1", "manual", "deterministic", "v3");
 REQUIRE(run_id == 1);
 std::vector<RankedCandidate> ranked{Ranked("m1", 0.8), Ranked("m2", 0.4)};
 repository.InsertCandidates(*session, run_id, "txn-1", ranked, {"m1"});
 repository.UpdateRunModelName(*session, run_id, "deterministic");
 auto summary = repository.ReadLastRunSummary(*session, "txn-1");
 REQUIRE(summary.has_value());
 REQUIRE((*summary)["match_run_id"] == 1);
 REQUIRE((*summary)["status"] == "needs_review");
 REQUIRE((*summary)["prompt_version"] == "v3");
 REQUIRE((*summary)["candidate_cache_rows"].size() == 2);
 nlohmann::json row = (*summary)["candidate_cache_rows"][0];
 REQUIRE(row["email_message_id"] == "m1");
 REQUIRE(row["score"].get<double>() == Approx(0.8));
 REQUIRE(row["reason_json"]["merchant_overlap"].get<double>() == Approx(0.5));
 REQUIRE(row["is_unmatched_email_priority"] == true);
 REQUIRE(row["email_received_at"] == "2024-06-01T15:00:00");
 session->Complete();
}

TEST_CASE("persist_ai_result inserts confident match and updates run", "[repository]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 long long run_id = repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
 std::vector<RankedCandidate> ranked{Ranked("m1", 0.95)};
 AiSelection selection({"m1"}, 0.95, false, "clear match", "anthropic", "model");
 std::vector<std::string> selected = repository.PersistAiResult(*session, "txn-1", run_id, ranked, selection, 0.90);
 REQUIRE(selected == std::vector<std::string>{"m1"});
 auto active = repository.ReadActiveMatchSummary(*session, "txn-1");
 REQUIRE(active.has_value());
 REQUIRE((*active)["state"] == "ai_match_confident");
 REQUIRE((*active)["email_message_id"] == "m1");
 REQUIRE((*active)["ai_confidence"].get<double>() == Approx(0.95));
 auto summary = repository.ReadLastRunSummary(*session, "txn-1");
 REQUIRE((*summary)["status"] == "succeeded");
 session->Complete();
}

TEST_CASE("persist_ai_result records no-match and uncertain conflicts", "[repository]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 long long no_match_run = repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
 AiSelection none({}, 0.1, true, "nothing fits", "anthropic", "model");
 REQUIRE(repository.PersistAiResult(*session, "txn-1", no_match_run, {}, none, 0.90).empty());
 auto active = repository.ReadActiveMatchSummary(*session, "txn-1");
 REQUIRE((*active)["state"] == "ai_no_match_found");
 REQUIRE((*active)["email_message_id"].is_null());
 REQUIRE((*repository.ReadLastRunSummary(*session, "txn-1"))["status"] == "no_candidates");
 // Attach m9 to txn-2 first, then select it for txn-1 -> conflict path.
 long long other_run = repository.CreateRun(*session, "txn-2", "manual", "model", "v3");
 AiSelection other({"m9"}, 0.95, false, "match", "anthropic", "model");
 repository.PersistAiResult(*session, "txn-2", other_run, {Ranked("m9", 0.95)}, other, 0.90);
 long long conflict_run = repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
 std::vector<std::string> selected =
  repository.PersistAiResult(*session, "txn-1", conflict_run, {Ranked("m9", 0.95)}, other, 0.90);
 REQUIRE(selected.empty());
 auto conflicted = repository.ReadActiveMatchSummary(*session, "txn-1");
 REQUIRE((*conflicted)["state"] == "ai_candidate_uncertain");
 REQUIRE((*conflicted)["email_message_id"].is_null());
 REQUIRE((*repository.ReadLastRunSummary(*session, "txn-1"))["status"] == "needs_review");
 std::set<std::string> taken = repository.ListActiveEmailIdsForOtherTransactions(*session, "txn-1");
 REQUIRE(taken.count("m9") == 1);
 session->Complete();
}

TEST_CASE("pending list returns unsettled transactions deterministically", "[repository]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 std::vector<std::string> pending = repository.ListPendingTransactionIds(*session, 100, 14);
 REQUIRE(pending.size() == 2); // never matched -> both queued (lookback bypassed via lr IS NULL)
 long long run_id = repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
 AiSelection confident({"m1"}, 0.95, false, "match", "anthropic", "model");
 repository.PersistAiResult(*session, "txn-1", run_id, {Ranked("m1", 0.95)}, confident, 0.90);
 std::vector<std::string> after = repository.ListPendingTransactionIds(*session, 100, 14);
 REQUIRE(after == std::vector<std::string>{"txn-2"});
 session->Complete();
}

TEST_CASE("human confirm deactivates prior matches and inserts confirmed row", "[repository]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 auto session = repository.OpenSession();
 long long run_id = repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
 AiSelection selection({"m1"}, 0.95, false, "match", "anthropic", "model");
 repository.PersistAiResult(*session, "txn-1", run_id, {Ranked("m1", 0.95)}, selection, 0.90);
 repository.DeactivateActiveMatch(*session, "txn-1");
 long long match_id = repository.InsertHumanConfirmedMatch(*session, "txn-1", "m1", std::string("looks right"));
 REQUIRE(match_id > 0);
 auto active = repository.ReadActiveMatchSummary(*session, "txn-1");
 REQUIRE((*active)["state"] == "human_confirmed_ai_match");
 REQUIRE((*active)["selected_by"] == "human");
 session->Complete();
}

TEST_CASE("write-disabled sessions roll back", "[repository]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository(false);
 { auto session = repository.OpenSession();
  repository.CreateRun(*session, "txn-1", "manual", "model", "v3");
  session->Complete(); // write disabled -> rollback
 }
 auto session = repository.OpenSession();
 REQUIRE_FALSE(repository.ReadLastRunSummary(*session, "txn-1").has_value());
 session->Complete();
}

TEST_CASE("cache hash and cached response flow", "[repository][caching]")
{ matchycore::testfx::Fixture fixture;
 db::MatchRepository repository = fixture.Repository();
 std::vector<RankedCandidate> ranked{Ranked("m1", 0.95)};
 nlohmann::json rows = caching::RankedCandidateCacheRows(ranked);
 REQUIRE(rows.size() == 1);
 REQUIRE(rows[0]["email_message_id"] == "m1");
 std::string hash_a = caching::CandidateSetHash(rows);
 std::string hash_b = caching::CandidateSetHash(caching::RankedCandidateCacheRows(ranked));
 REQUIRE(hash_a == hash_b);
 REQUIRE(hash_a.size() == 64);
 REQUIRE(caching::CandidateMessageIdHash({"b", "a"}) == caching::CandidateMessageIdHash({"a", "b"}));
 auto session = repository.OpenSession();
 long long run_id = repository.CreateRun(*session, "txn-1", "manual", "deterministic", "v3");
 repository.InsertCandidates(*session, run_id, "txn-1", ranked, {"m1"});
 AiSelection selection({"m1"}, 0.95, false, "match", "deterministic", "deterministic");
 repository.PersistAiResult(*session, "txn-1", run_id, ranked, selection, 0.90);
 // Hash of stored rows differs from the live ranked rows (naive DB timestamps), mirroring the
 // Python-on-sqlite behavior; a cache hit therefore requires the stored-row hash.
 auto stored = repository.ReadLastRunSummary(*session, "txn-1");
 std::string stored_hash = caching::CandidateSetHash((*stored)["candidate_cache_rows"]);
 auto cached = caching::MaybeCachedResponse(repository, *session, "txn-1", 1, "deterministic",
                                            stored_hash, "", false);
 REQUIRE(cached.has_value());
 REQUIRE((*cached)["skipped"] == true);
 REQUIRE((*cached)["run_id"] == run_id);
 REQUIRE((*cached)["selected_message_ids"] == nlohmann::json::array({"m1"}));
 auto forced = caching::MaybeCachedResponse(repository, *session, "txn-1", 1, "deterministic",
                                            stored_hash, "", true);
 REQUIRE_FALSE(forced.has_value());
 auto wrong_model = caching::MaybeCachedResponse(repository, *session, "txn-1", 1, "claude",
                                                 stored_hash, "", false);
 REQUIRE_FALSE(wrong_model.has_value());
 session->Complete();
}

TEST_CASE("sha256 matches python hashlib pins", "[caching]")
{ // python: hashlib.sha256(b"a\n").hexdigest()
 REQUIRE(caching::CandidateMessageIdHash({"a"})
         == "87428fc522803d31065e7bce3cf03fe475096631e5e07bbd7a0fde60c4cf25c7");
}
