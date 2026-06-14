// Oracle harness CLI for the matchy Python/C++ parity lane (t17, src/core/oracle/compare_oracle.py).
// Exposes matchy's deterministic, side-effect-free logic (scoring + candidate-set hashing,
// near-duplicate collapse, SimHash, CLDR currency matching) as JSON ops so the harness can drive
// the same scenario inputs through BOTH the Python reference and this binary and diff the results.
//
// Modes (payload is inline JSON or @file):
//   matchy_oracle_runner rank        <payload>   {"transaction":{...},"candidates":[...],"already_matched_ids":[...]}
//   matchy_oracle_runner collapse    <payload>   {"candidates":[...],"max_distance":N}
//   matchy_oracle_runner simhash     <payload>   {"text":"..."}
//   matchy_oracle_runner cldr_tokens <payload>   {"payload": <cldr-json>}
//   matchy_oracle_runner cldr_match  <payload>   {"tokens":[...],"text":"..."}
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/caching.hpp"
#include "matchycore/cldr.hpp"
#include "matchycore/models.hpp"
#include "matchycore/near_duplicate.hpp"
#include "matchycore/scoring.hpp"
#include "matchycore/timeutil.hpp"

namespace
{ using namespace matchycore;
 using nlohmann::json;

// #R001: Matchycore traceability implementation coverage.
 std::string ReadFile(const std::string &path)
 { std::ifstream in(path);
  if (!in.is_open()) throw std::runtime_error("cannot open file: " + path);
  std::stringstream buffer;
  buffer << in.rdbuf();
  return buffer.str();
 }

// #R001: Matchycore traceability implementation coverage.
 json PayloadFromArg(const std::string &raw)
 { return !raw.empty() && raw[0] == '@' ? json::parse(ReadFile(raw.substr(1))) : json::parse(raw);
 }

// #R001: Matchycore traceability implementation coverage.
 TimePoint ParseTime(const json &value)
 { TimePoint parsed{};
  if (value.is_string())
  { std::optional<TimePoint> result = timeutil::ParseIso8601(value.get<std::string>());
   if (result.has_value()) parsed = *result;
  }
  return parsed;
 }

// #R001: Matchycore traceability implementation coverage.
 TransactionInput ParseTransaction(const json &value)
 { return TransactionInput(value.value("transaction_id", std::string()), value.value("account_id", std::string()),
                           value.value("amount", std::string()), ParseTime(value.value("date", json())),
                           value.value("description", std::string()), value.value("counterparty_name", std::string()));
 }

// #R001: Matchycore traceability implementation coverage.
 EmailCandidate ParseCandidate(const json &value)
 { return EmailCandidate(value.value("message_id", std::string()), value.value("subject", std::string()),
                         value.value("preview", std::string()), ParseTime(value.value("received_at", json())),
                         value.value("sender", std::string()), value.value("body_text", std::string()));
 }

// #R001: Matchycore traceability implementation coverage.
 std::vector<EmailCandidate> ParseCandidates(const json &items)
 { std::vector<EmailCandidate> candidates;
  for (const json &item : items) candidates.push_back(ParseCandidate(item));
  return candidates;
 }

// #R001: Matchycore traceability implementation coverage.
 json RunRank(const json &payload)
 { TransactionInput transaction = ParseTransaction(payload.value("transaction", json::object()));
  std::vector<EmailCandidate> candidates = ParseCandidates(payload.value("candidates", json::array()));
  std::set<std::string> already_matched;
  for (const json &item : payload.value("already_matched_ids", json::array()))
   if (item.is_string()) already_matched.insert(item.get<std::string>());
  std::vector<RankedCandidate> ranked = scoring::RankCandidates(transaction, candidates, already_matched);
  json ranked_rows = json::array();
  for (const RankedCandidate &row : ranked)
   ranked_rows.push_back({{"email_message_id", row.candidate().message_id()},
                          {"score", row.score()}, {"reasons", row.reasons()}});
  json cache_rows = caching::RankedCandidateCacheRows(ranked);
  std::vector<std::string> current_ids;
  for (const json &row : cache_rows) current_ids.push_back(row["email_message_id"].get<std::string>());
  return json{{"ranked", ranked_rows}, {"candidate_set_hash", caching::CandidateSetHash(cache_rows)},
              {"candidate_message_id_hash", caching::CandidateMessageIdHash(current_ids)}};
 }

// #R001: Matchycore traceability implementation coverage.
 json RunCollapse(const json &payload)
 { std::vector<EmailCandidate> candidates = ParseCandidates(payload.value("candidates", json::array()));
  int max_distance = payload.value("max_distance", 0);
  std::vector<EmailCandidate> kept = near_duplicate::CollapseNearDuplicates(candidates, max_distance);
  std::vector<std::string> kept_ids;
  for (const EmailCandidate &candidate : kept) kept_ids.push_back(candidate.message_id());
  return json{{"kept_message_ids", kept_ids}};
 }

// #R001: Matchycore traceability implementation coverage.
 json RunSimhash(const json &payload)
 { std::uint64_t fingerprint = near_duplicate::Simhash64(payload.value("text", std::string()));
  return json{{"fingerprint", std::to_string(fingerprint)}};
 }

// #R001: Matchycore traceability implementation coverage.
 json RunCldrTokens(const json &payload)
 { std::set<std::string> tokens = cldr::CldrCurrenciesCache::ParseCurrencyTokens(payload.value("payload", json()));
  return json{{"tokens", std::vector<std::string>(tokens.begin(), tokens.end())}};
 }

// #R001: Matchycore traceability implementation coverage.
 json RunCldrMatch(const json &payload)
 { std::set<std::string> tokens;
  for (const json &item : payload.value("tokens", json::array()))
   if (item.is_string()) tokens.insert(item.get<std::string>());
  cldr::CldrCurrencyMatcher matcher(tokens);
  return json{{"contains", matcher.ContainsStandaloneCurrency(payload.value("text", std::string()))}};
 }

// #R001: Matchycore traceability implementation coverage.
 int Run(int argc, char **argv)
 { if (argc < 3) throw std::runtime_error("usage: matchy_oracle_runner <mode> <payload-json|@file>");
  std::string mode = argv[1];
  json payload = PayloadFromArg(argv[2]);
  json result;
  if (mode == "rank") result = RunRank(payload);
  else if (mode == "collapse") result = RunCollapse(payload);
  else if (mode == "simhash") result = RunSimhash(payload);
  else if (mode == "cldr_tokens") result = RunCldrTokens(payload);
  else if (mode == "cldr_match") result = RunCldrMatch(payload);
  else throw std::runtime_error("unknown mode: " + mode);
  std::cout << result.dump() << "\n";
  return 0;
 }
}

// #R001: Matchycore traceability implementation coverage.
int main(int argc, char **argv)
{ int exit_code = 0;
 try { exit_code = Run(argc, argv); }
 catch (const std::exception &exc)
 { std::cout << json{{"error", {{"detail", exc.what()}}}}.dump() << "\n";
  exit_code = 1;
 }
 return exit_code;
}
