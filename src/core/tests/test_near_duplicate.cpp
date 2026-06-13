// Port of tests/py/test_near_duplicate.py (R055 SimHash collapsing contracts).
#include <catch2/catch_test_macros.hpp>
#include <chrono>
#include "matchycore/near_duplicate.hpp"

using matchycore::EmailCandidate;
namespace nd = matchycore::near_duplicate;

namespace
{ const matchycore::TimePoint kTime = std::chrono::system_clock::from_time_t(1777950000);
}

TEST_CASE("simhash64 deterministic and content sensitive", "[near_duplicate]")
{ std::string receipt = "Starbucks coffee order total confirmation receipt amount";
 REQUIRE(nd::Simhash64(receipt) == nd::Simhash64(receipt));
 REQUIRE(nd::Simhash64("") == 0);
 REQUIRE(nd::HammingDistance(nd::Simhash64(receipt), nd::Simhash64("gardening newsletter weekly unrelated topics")) > 3);
}

TEST_CASE("simhash matches python blake2b digest_size=8 pins", "[near_duplicate]")
{ // For a single-token text the fingerprint equals the token hash; pins from Python's
 // int.from_bytes(hashlib.blake2b(token, digest_size=8).digest(), "big").
 REQUIRE(nd::Simhash64("coffee") == 8734595519710172668ULL);
 REQUIRE(nd::Simhash64("starbucks") == 8331483935328088530ULL);
 REQUIRE(nd::Simhash64(std::string(200, 'a')) == 12973453062473729138ULL);
}

TEST_CASE("hamming distance counts differing bits", "[near_duplicate]")
{ REQUIRE(nd::HammingDistance(0b1011, 0b0001) == 2);
 REQUIRE(nd::HammingDistance(42, 42) == 0);
}

TEST_CASE("collapse merges clusters and preserves distinct", "[near_duplicate]")
{ std::string body = "Starbucks coffee order total confirmation receipt amount due today";
 EmailCandidate first("a", "Receipt", "", kTime, "x@y", body);
 EmailCandidate forwarded("b", "Receipt", "", kTime, "x@y", body);
 EmailCandidate unrelated("c", "News", "", kTime, "z@w", "gardening newsletter weekly unrelated topics here");
 std::vector<EmailCandidate> collapsed = nd::CollapseNearDuplicates({first, forwarded, unrelated}, 3);
 REQUIRE(collapsed.size() == 2);
 REQUIRE(collapsed[0].message_id() == "a");
 REQUIRE(collapsed[1].message_id() == "c");
}

TEST_CASE("collapse is noop when disabled or trivial", "[near_duplicate]")
{ EmailCandidate a("a", "Receipt", "", kTime, "x@y", "same body text here");
 EmailCandidate b("b", "Receipt", "", kTime, "x@y", "same body text here");
 std::vector<EmailCandidate> unchanged = nd::CollapseNearDuplicates({a, b}, 0);
 REQUIRE(unchanged.size() == 2);
 std::vector<EmailCandidate> single = nd::CollapseNearDuplicates({a}, 3);
 REQUIRE(single.size() == 1);
 REQUIRE(single[0].message_id() == "a");
}
