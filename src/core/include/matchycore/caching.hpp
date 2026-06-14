#pragma once
#include <optional>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/models.hpp"
#include "matchycore/repository.hpp"

// Port of matchy/caching.py (AI-skip cache keyed on candidate signature + model + prompt version).
namespace matchycore::caching
{ // #R001: Normalize ranked candidates into cache rows (score, reasons, cached metadata).
 nlohmann::json RankedCandidateCacheRows(const std::vector<RankedCandidate> &ranked_candidates);

 // #R001: Order-independent SHA-256 fingerprint of full candidate cache rows.
 std::string CandidateSetHash(const nlohmann::json &candidate_cache_rows);

 // #R001: Deterministic fallback hash from sorted candidate message ids.
 std::string CandidateMessageIdHash(const std::vector<std::string> &message_ids);

 // #R001: Cached response (skipped=true) when the prior verdict still applies, else nullopt.
 std::optional<nlohmann::json> MaybeCachedResponse(const db::MatchRepository &repository, db::Session &session,
                                                   const std::string &transaction_id, std::size_t candidate_count,
                                                   const std::string &planned_model, const std::string &current_hash,
                                                   const std::string &current_message_id_hash, bool force_rematch);
}
