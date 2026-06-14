#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "matchycore/models.hpp"

// Port of matchy/near_duplicate.py (SimHash collapse of forwarded/marketing receipt variants).
namespace matchycore::near_duplicate
{ // #R001: 64-bit SimHash over a text's long tokens; per-token bits come from BLAKE2b(digest_size=8).
 std::uint64_t Simhash64(const std::string &text);

 // #R001: Count of differing bits between two fingerprints.
 int HammingDistance(std::uint64_t left, std::uint64_t right);

 // #R001: Keep the first representative of each near-duplicate cluster; zero fingerprints never collapse;
 // #R001: a non-positive threshold is a no-op.
 std::vector<EmailCandidate> CollapseNearDuplicates(const std::vector<EmailCandidate> &candidates, int max_distance);
}
