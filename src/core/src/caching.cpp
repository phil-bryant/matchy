#include "matchycore/caching.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <set>
#include "matchycore/ai_ranker.hpp"
#include "matchycore/timeutil.hpp"

namespace matchycore::caching
{ namespace
 { //R020: Completed-evaluation statuses; `failed` is excluded so transient errors self-heal.
  const std::set<std::string> kCacheHitStatuses{"succeeded", "needs_review", "no_candidates"};

  // Compact SHA-256 (FIPS 180-4) so caching does not depend on OpenSSL in DB-only builds.
  class Sha256
  { public:
   void Update(const std::string &data)
   { for (char c : data) Byte(static_cast<std::uint8_t>(c));
   }

   std::string Hexdigest()
   { std::uint64_t bit_length = total_ * 8;
    Byte(0x80, true);
    while (buffer_len_ != 56) Byte(0x00, true);
    for (int shift = 56; shift >= 0; shift -= 8) Byte(static_cast<std::uint8_t>(bit_length >> shift), true);
    char out[65];
    for (int i = 0; i < 8; i += 1) std::snprintf(out + i * 8, 9, "%08x", h_[static_cast<std::size_t>(i)]);
    return std::string(out, 64);
   }

   private:
   void Byte(std::uint8_t value, bool padding = false)
   { buffer_[buffer_len_] = value;
    buffer_len_ += 1;
    if (!padding) total_ += 1;
    if (buffer_len_ == 64)
    { Compress();
     buffer_len_ = 0;
    }
   }

   static std::uint32_t Rotr(std::uint32_t x, unsigned n) { return (x >> n) | (x << (32 - n)); }

   void Compress()
   { static constexpr std::array<std::uint32_t, 64> k =
    { 0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
      0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
      0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
      0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
      0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2 };
    std::array<std::uint32_t, 64> w{};
    for (int i = 0; i < 16; i += 1)
     w[static_cast<std::size_t>(i)] = (static_cast<std::uint32_t>(buffer_[i * 4]) << 24)
      | (static_cast<std::uint32_t>(buffer_[i * 4 + 1]) << 16)
      | (static_cast<std::uint32_t>(buffer_[i * 4 + 2]) << 8) | buffer_[i * 4 + 3];
    for (int i = 16; i < 64; i += 1)
    { std::uint32_t s0 = Rotr(w[static_cast<std::size_t>(i - 15)], 7) ^ Rotr(w[static_cast<std::size_t>(i - 15)], 18)
      ^ (w[static_cast<std::size_t>(i - 15)] >> 3);
     std::uint32_t s1 = Rotr(w[static_cast<std::size_t>(i - 2)], 17) ^ Rotr(w[static_cast<std::size_t>(i - 2)], 19)
      ^ (w[static_cast<std::size_t>(i - 2)] >> 10);
     w[static_cast<std::size_t>(i)] = w[static_cast<std::size_t>(i - 16)] + s0 + w[static_cast<std::size_t>(i - 7)] + s1;
    }
    std::uint32_t a = h_[0], b = h_[1], c = h_[2], d = h_[3], e = h_[4], f = h_[5], g = h_[6], h = h_[7];
    for (int i = 0; i < 64; i += 1)
    { std::uint32_t s1 = Rotr(e, 6) ^ Rotr(e, 11) ^ Rotr(e, 25);
     std::uint32_t ch = (e & f) ^ (~e & g);
     std::uint32_t temp1 = h + s1 + ch + k[static_cast<std::size_t>(i)] + w[static_cast<std::size_t>(i)];
     std::uint32_t s0 = Rotr(a, 2) ^ Rotr(a, 13) ^ Rotr(a, 22);
     std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
     std::uint32_t temp2 = s0 + maj;
     h = g;
     g = f;
     f = e;
     e = d + temp1;
     d = c;
     c = b;
     b = a;
     a = temp1 + temp2;
    }
    h_[0] += a;
    h_[1] += b;
    h_[2] += c;
    h_[3] += d;
    h_[4] += e;
    h_[5] += f;
    h_[6] += g;
    h_[7] += h;
   }

   std::array<std::uint32_t, 8> h_{0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                   0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
   std::uint8_t buffer_[64] = {0};
   std::size_t buffer_len_ = 0;
   std::uint64_t total_ = 0;
  };

  std::string JsonString(const nlohmann::json &row, const char *key)
  { std::string out;
   if (row.contains(key) && row[key].is_string()) out = row[key].get<std::string>();
   return out;
  }
 }

 nlohmann::json RankedCandidateCacheRows(const std::vector<RankedCandidate> &ranked_candidates)
 { nlohmann::json rows = nlohmann::json::array();
  for (const RankedCandidate &ranked : ranked_candidates)
  { const EmailCandidate &candidate = ranked.candidate();
   std::string preview = candidate.preview().empty()
    ? (candidate.body_text().empty() ? candidate.preview() : candidate.body_text().substr(0, 240))
    : candidate.preview();
   rows.push_back({
    {"email_message_id", candidate.message_id()},
    {"email_received_at", timeutil::FormatIsoUtc(candidate.received_at())},
    {"score", ranked.score()},
    {"reason_json", ranked.reasons()},
    {"cached_subject", candidate.subject()},
    {"cached_sender", candidate.sender()},
    {"cached_snippet", preview},
    {"is_unmatched_email_priority", ranked.reasons().value("unmatched_email_priority", false)}});
  }
  return rows;
 }

 std::string CandidateSetHash(const nlohmann::json &candidate_cache_rows)
 { std::vector<nlohmann::json> normalized_rows;
  for (const nlohmann::json &row : candidate_cache_rows)
  { double score = 0.0;
   if (row.contains("score") && row["score"].is_number()) score = row["score"].get<double>();
   char score_text[32];
   std::snprintf(score_text, sizeof(score_text), "%0.8f", score);
   nlohmann::json reason = nlohmann::json::object();
   if (row.contains("reason_json") && row["reason_json"].is_object()) reason = row["reason_json"];
   normalized_rows.push_back({
    {"email_message_id", JsonString(row, "email_message_id")},
    {"email_received_at", JsonString(row, "email_received_at")},
    {"score", std::string(score_text)},
    {"reason_json", reason},
    {"cached_subject", JsonString(row, "cached_subject")},
    {"cached_sender", JsonString(row, "cached_sender")},
    {"cached_snippet", JsonString(row, "cached_snippet")},
    {"is_unmatched_email_priority", row.contains("is_unmatched_email_priority")
     && row["is_unmatched_email_priority"].is_boolean() && row["is_unmatched_email_priority"].get<bool>()}});
  }
  std::stable_sort(normalized_rows.begin(), normalized_rows.end(),
                   [](const nlohmann::json &a, const nlohmann::json &b)
                   { auto key = [](const nlohmann::json &row)
                     { return std::make_tuple(row["email_message_id"].get<std::string>(),
                                              row["email_received_at"].get<std::string>(),
                                              row["cached_snippet"].get<std::string>());
                     };
                    return key(a) < key(b);
                   });
  Sha256 digest;
  for (const nlohmann::json &row : normalized_rows)
  { digest.Update(row.dump());
   digest.Update("\n");
  }
  return digest.Hexdigest();
 }

 std::string CandidateMessageIdHash(const std::vector<std::string> &message_ids)
 { std::vector<std::string> sorted_ids = message_ids;
  std::sort(sorted_ids.begin(), sorted_ids.end());
  Sha256 digest;
  for (const std::string &message_id : sorted_ids)
  { digest.Update(message_id);
   digest.Update("\n");
  }
  return digest.Hexdigest();
 }

 std::optional<nlohmann::json> MaybeCachedResponse(const db::MatchRepository &repository, db::Session &session,
                                                   const std::string &transaction_id, std::size_t candidate_count,
                                                   const std::string &planned_model, const std::string &current_hash,
                                                   const std::string &current_message_id_hash, bool force_rematch)
 { std::optional<nlohmann::json> response;
  bool eligible = !force_rematch;
  std::optional<nlohmann::json> last_summary;
  if (eligible)
  { last_summary = repository.ReadLastRunSummary(session, transaction_id);
   eligible = last_summary.has_value();
  }
  if (eligible) eligible = kCacheHitStatuses.count((*last_summary)["status"].get<std::string>()) > 0;
  if (eligible) eligible = (*last_summary)["model_name"].get<std::string>() == planned_model;
  if (eligible) eligible = (*last_summary)["prompt_version"].get<std::string>() == ai::kPromptVersion;
  if (eligible)
  { if ((*last_summary).contains("candidate_cache_rows") && !(*last_summary)["candidate_cache_rows"].is_null())
    eligible = CandidateSetHash((*last_summary)["candidate_cache_rows"]) == current_hash;
   else
   { std::vector<std::string> cached_ids;
    if ((*last_summary).contains("candidate_message_ids"))
     for (const nlohmann::json &item : (*last_summary)["candidate_message_ids"])
      cached_ids.push_back(item.is_string() ? item.get<std::string>() : item.dump());
    eligible = CandidateMessageIdHash(cached_ids) == current_message_id_hash;
   }
  }
  if (eligible)
  { std::optional<nlohmann::json> active = repository.ReadActiveMatchSummary(session, transaction_id);
   nlohmann::json active_row = active.has_value() ? *active : nlohmann::json::object();
   std::string state = active_row.value("state", "");
   if (state != "ai_no_match_found")
   { nlohmann::json selected_ids = nlohmann::json::array();
    if (active_row.contains("email_message_id") && active_row["email_message_id"].is_string())
     selected_ids.push_back(active_row["email_message_id"].get<std::string>());
    response = nlohmann::json{
     {"transaction_id", transaction_id},
     {"run_id", (*last_summary)["match_run_id"]},
     {"selected_message_ids", selected_ids},
     {"candidate_count", candidate_count},
     {"ai_confidence", active_row.contains("ai_confidence") ? active_row["ai_confidence"] : nlohmann::json()},
     {"uncertain", nullptr},
     {"skipped", true},
     {"skip_reason", "candidate_signature_unchanged_for_model_and_prompt"},
     {"state", active_row.contains("state") ? active_row["state"] : nlohmann::json()}};
   }
  }
  return response;
 }
}
