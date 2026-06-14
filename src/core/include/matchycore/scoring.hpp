#pragma once
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>
#include "matchycore/models.hpp"

// Port of matchy/scoring_core.py and matchy/scoring.py (deterministic ranking heuristics).
namespace matchycore::scoring
{ // #R001: R010: Normalize text to lowercase with non [a-z0-9 whitespace] bytes replaced by spaces.
 std::string NormalizedText(const std::string &value);

 // #R001: Token overlap over long tokens (length > 2): intersection divided by the larger token-set size.
 double TokenOverlap(const std::string &left, const std::string &right);

 // #R001: Parse a decimal string and return absolute integer cents using half-up rounding, or nullopt on invalid input.
 std::optional<long long> DecimalToCents(const std::string &value);

 // #R001: Extract money-like numeric tokens (optionally $-prefixed, comma-grouped, 0-2 decimals) as integer cents.
 std::set<long long> ExtractMoneyCents(const std::string &text);

 // #R001: Exact integer-cents hint between the transaction amount and any money token in candidate text.
 double AmountHintScore(const std::string &amount, const EmailCandidate &candidate);

 // #R001: Binary long-token overlap between transaction text and sender text.
 double SenderHintScore(const std::string &transaction_text, const std::string &sender);

 // #R001: Binary hint when a long (>=6 chars, non-digit) transaction token appears in compacted candidate text.
 double CompactMerchantHintScore(const std::string &transaction_text, const std::string &candidate_text);

 // #R001: Map absolute hour distance to the documented proximity buckets.
 double TimeProximityScore(TimePoint txn_time, TimePoint received_at);

 // #R001: Tokenize normalized text into long tokens preserving repeats for term frequency.
 std::vector<std::string> RelevanceTokens(const std::string &value);

 // #R001: Count how many corpus documents contain each long token at least once.
 std::map<std::string, int> DocumentFrequencies(const std::vector<std::string> &documents);

 // #R001: Smoothed BM25 inverse document frequency.
 double InverseDocumentFrequency(int corpus_size, int document_frequency);

 // #R001: Okapi BM25 relevance of a query against one document using corpus statistics.
 double Bm25Score(const std::string &query, const std::string &document, int corpus_size,
                  const std::map<std::string, int> &document_frequency_map, double average_document_length,
                  double k1 = 1.5, double b = 0.75);

 // #R001: Saturate a non-negative BM25 score into the unit interval.
 double Bm25Relevance(double score, double saturation = 4.0);

 // #R001: Subset-sum reachability over positive integer-cent amounts within an inclusive tolerance band.
 bool SubsetSumReachable(const std::vector<long long> &amounts_cents, long long target_cents,
                         long long tolerance_cents = 0);

 // #R001: Reconciliation signal when smaller line items can sum to the transaction total.
 double AmountReconciliationScore(const std::string &amount, const EmailCandidate &candidate, int max_terms = 12);

 // Match Python round(value, 4) (round-half-even on the decimal expansion of the double).
 double Round4(double value);

 // #R001: R047: Rank candidates by the weighted heuristic blend, sorted by descending score (stable).
 std::vector<RankedCandidate> RankCandidates(const TransactionInput &transaction,
                                             const std::vector<EmailCandidate> &candidates,
                                             const std::set<std::string> &already_matched_ids);
}
