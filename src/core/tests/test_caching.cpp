// Focused unit coverage for matchycore::caching pure helpers (candidate-set hashing + cache rows),
// complementing the DB round-trip assertions in test_repository.cpp.
#include <catch2/catch_test_macros.hpp>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/caching.hpp"
#include "matchycore/models.hpp"
#include "matchycore/timeutil.hpp"

using matchycore::EmailCandidate;
using matchycore::RankedCandidate;
namespace caching = matchycore::caching;

namespace
{ const matchycore::TimePoint kWhen = *matchycore::timeutil::ParseIso8601("2024-06-01T15:00:00+00:00");

// #R001: Build a ranked candidate fixture with a stable received-at and reasons map.
 RankedCandidate Ranked(const std::string &id, double score)
 { return RankedCandidate(EmailCandidate(id, "Receipt " + id, "preview", kWhen, "shop@x.com", "body"), score,
                          {{"merchant_overlap", 0.5}});
 }
}

TEST_CASE("CandidateMessageIdHash is order-independent and content-sensitive", "[caching]")
{ std::string ordered = caching::CandidateMessageIdHash({"m1", "m2", "m3"});
 std::string shuffled = caching::CandidateMessageIdHash({"m3", "m1", "m2"});
 std::string smaller = caching::CandidateMessageIdHash({"m1", "m2"});
 REQUIRE(ordered == shuffled);
 REQUIRE(ordered != smaller);
 REQUIRE(ordered.size() == 64);
}

TEST_CASE("CandidateSetHash is order-independent and content-sensitive", "[caching]")
{ nlohmann::json rows = caching::RankedCandidateCacheRows({Ranked("m1", 0.8), Ranked("m2", 0.4)});
 nlohmann::json reordered = caching::RankedCandidateCacheRows({Ranked("m2", 0.4), Ranked("m1", 0.8)});
 nlohmann::json rescored = caching::RankedCandidateCacheRows({Ranked("m1", 0.9), Ranked("m2", 0.4)});
 REQUIRE(caching::CandidateSetHash(rows) == caching::CandidateSetHash(reordered));
 REQUIRE(caching::CandidateSetHash(rows) != caching::CandidateSetHash(rescored));
}

TEST_CASE("RankedCandidateCacheRows projects message id and score", "[caching]")
{ nlohmann::json rows = caching::RankedCandidateCacheRows({Ranked("m1", 0.8)});
 REQUIRE(rows.is_array());
 REQUIRE(rows.size() == 1);
 REQUIRE(rows[0]["email_message_id"] == "m1");
 REQUIRE(rows[0]["score"].get<double>() == 0.8);
}
