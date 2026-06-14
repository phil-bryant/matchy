#include "matchycore/scoring.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace matchycore::scoring
{ namespace
// #R001: Matchycore traceability implementation coverage.
 { bool IsDigit(char c) { return c >= '0' && c <= '9'; }

// #R001: Matchycore traceability implementation coverage.
  bool IsSpace(char c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v'; }

// #R001: Matchycore traceability implementation coverage.
  std::vector<std::string> SplitWhitespace(const std::string &value)
  { std::vector<std::string> parts;
   std::string current;
   for (char c : value)
   { if (IsSpace(c))
    { if (!current.empty()) parts.push_back(current);
     current.clear();
    }
    else current.push_back(c);
   }
   if (!current.empty()) parts.push_back(current);
   return parts;
  }

// #R001: Matchycore traceability implementation coverage.
  std::set<std::string> LongTokens(const std::string &value, std::size_t min_exclusive)
  { std::set<std::string> tokens;
   for (const std::string &part : SplitWhitespace(NormalizedText(value)))
    if (part.size() > min_exclusive) tokens.insert(part);
   return tokens;
  }

  // Decimal parsed into a digit string (leading zeros stripped) and scale = digits after the point,
  // adjusted by any exponent. Mirrors what Python Decimal stores as (coefficient, exponent).
  class ParsedDecimal
  { public:
// #R001: Matchycore traceability implementation coverage.
   ParsedDecimal(bool valid, std::string digits, long long scale)
   : valid_(valid), digits_(std::move(digits)), scale_(scale) {}
// #R001: Matchycore traceability implementation coverage.
   [[nodiscard]] bool valid() const { return valid_; }
// #R001: Matchycore traceability implementation coverage.
   [[nodiscard]] const std::string &digits() const { return digits_; }
// #R001: Matchycore traceability implementation coverage.
   [[nodiscard]] long long scale() const { return scale_; }

   private:
   bool valid_;
   std::string digits_;
   long long scale_;
  };

// #R001: Matchycore traceability implementation coverage.
  ParsedDecimal ParseDecimal(const std::string &value)
  { std::size_t i = 0;
   bool ok = !value.empty();
   if (ok && (value[i] == '+' || value[i] == '-')) i += 1;
   std::string digits;
   long long scale = 0;
   bool seen_digit = false, seen_dot = false, scanning = true;
   while (scanning && i < value.size())
   { char c = value[i];
    if (IsDigit(c))
    { digits.push_back(c);
     if (seen_dot) scale += 1;
     seen_digit = true;
     i += 1;
    }
    else if (c == '.' && !seen_dot)
    { seen_dot = true;
     i += 1;
    }
    else scanning = false;
   }
   if (ok && seen_digit && i < value.size() && (value[i] == 'e' || value[i] == 'E'))
   { i += 1;
    bool exp_negative = false;
    if (i < value.size() && (value[i] == '+' || value[i] == '-'))
    { exp_negative = value[i] == '-';
     i += 1;
    }
    long long exponent = 0;
    bool exp_digit = false;
    while (i < value.size() && IsDigit(value[i]) && exponent <= 1000000)
    { exponent = exponent * 10 + (value[i] - '0');
     exp_digit = true;
     i += 1;
    }
    ok = ok && exp_digit;
    if (exp_negative) scale += exponent;
    else scale -= exponent;
   }
   ok = ok && seen_digit && i == value.size();
   std::size_t first_significant = digits.find_first_not_of('0');
   if (first_significant == std::string::npos) digits = "0";
   else digits = digits.substr(first_significant);
   return ParsedDecimal(ok, digits, scale);
  }

  // One regex-equivalent money-token match attempt at position q (first digit). Returns the end
  // offset of the numeric group, or npos. Mirrors the backtracking order of
  // ([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)(?!\d) in scoring_core.py.
// #R001: Matchycore traceability implementation coverage.
  std::size_t ConsecutiveDigits(const std::string &text, std::size_t pos)
  { std::size_t count = 0;
   while (pos + count < text.size() && IsDigit(text[pos + count])) count += 1;
   return count;
  }

// #R001: Matchycore traceability implementation coverage.
  bool LookaheadNotDigit(const std::string &text, std::size_t pos)
  { return pos >= text.size() || !IsDigit(text[pos]);
  }

// #R001: Matchycore traceability implementation coverage.
  std::size_t MatchFraction(const std::string &text, std::size_t pos)
  { std::size_t end = std::string::npos;
   if (pos < text.size() && text[pos] == '.')
   { std::size_t frac_digits = std::min<std::size_t>(ConsecutiveDigits(text, pos + 1), 2);
    bool searching = true;
    std::size_t take = frac_digits;
    while (searching && take >= 1)
    { if (LookaheadNotDigit(text, pos + 1 + take))
     { end = pos + 1 + take;
      searching = false;
     }
     else take -= 1;
    }
   }
   if (end == std::string::npos && LookaheadNotDigit(text, pos)) end = pos;
   return end;
  }

// #R001: Matchycore traceability implementation coverage.
  std::size_t MatchGroupedNumber(const std::string &text, std::size_t q)
  { std::size_t end = std::string::npos;
   std::size_t lead = std::min<std::size_t>(ConsecutiveDigits(text, q), 3);
   std::size_t first_len = lead;
   while (end == std::string::npos && first_len >= 1)
   { if (q + first_len < text.size() && text[q + first_len] == ',' && ConsecutiveDigits(text, q + first_len) == 0)
    { std::vector<std::size_t> group_ends;
     std::size_t pos = q + first_len;
     bool grouping = true;
     while (grouping && pos < text.size() && text[pos] == ',' && ConsecutiveDigits(text, pos + 1) >= 3)
     { pos += 4;
      group_ends.push_back(pos);
      grouping = ConsecutiveDigits(text, pos) == 0;
     }
     std::size_t group_index = group_ends.size();
     while (end == std::string::npos && group_index >= 1)
     { std::size_t fraction_end = MatchFraction(text, group_ends[group_index - 1]);
      if (fraction_end != std::string::npos) end = fraction_end;
      else group_index -= 1;
     }
    }
    if (end == std::string::npos) first_len -= 1;
   }
   return end;
  }

// #R001: Matchycore traceability implementation coverage.
  std::size_t MatchPlainNumber(const std::string &text, std::size_t q)
  { std::size_t digits = ConsecutiveDigits(text, q);
   std::size_t end = std::string::npos;
   if (digits >= 1) end = MatchFraction(text, q + digits);
   return end;
  }
 }

// #R001: Matchycore traceability implementation coverage.
 std::string NormalizedText(const std::string &value)
 { std::string out;
  out.reserve(value.size());
  for (char c : value)
  { unsigned char uc = static_cast<unsigned char>(c);
   if (uc >= 'A' && uc <= 'Z') out.push_back(static_cast<char>(uc - 'A' + 'a'));
   else if ((uc >= 'a' && uc <= 'z') || IsDigit(c) || IsSpace(c)) out.push_back(c);
   else out.push_back(' ');
  }
  return out;
 }

// #R001: Matchycore traceability implementation coverage.
 double TokenOverlap(const std::string &left, const std::string &right)
 { std::set<std::string> left_tokens = LongTokens(left, 2), right_tokens = LongTokens(right, 2);
  double result = 0.0;
  if (!left_tokens.empty() && !right_tokens.empty())
  { std::size_t overlap = 0;
   for (const std::string &token : left_tokens)
    if (right_tokens.count(token) > 0) overlap += 1;
   result = static_cast<double>(overlap) / static_cast<double>(std::max(left_tokens.size(), right_tokens.size()));
  }
  return result;
 }

// #R001: Matchycore traceability implementation coverage.
 std::optional<long long> DecimalToCents(const std::string &value)
 { ParsedDecimal parsed = ParseDecimal(value);
  std::optional<long long> result;
  if (parsed.valid())
  { std::string digits = parsed.digits();
   long long scale = parsed.scale();
   // Integer-digit blowups (e.g. 1E1000) raise InvalidOperation under Python's default precision.
   long long integer_digits = static_cast<long long>(digits.size()) - scale;
   if (integer_digits <= 18)
   { while (scale < 2)
    { digits.push_back('0');
     scale += 1;
    }
    long long drop = scale - 2;
    while (static_cast<long long>(digits.size()) < drop + 1) digits.insert(digits.begin(), '0');
    std::string kept = digits.substr(0, digits.size() - static_cast<std::size_t>(drop));
    bool round_up = drop > 0 && digits[digits.size() - static_cast<std::size_t>(drop)] >= '5';
    long long cents = 0;
    for (char c : kept) cents = cents * 10 + (c - '0');
    if (round_up) cents += 1;
    result = cents;
   }
  }
  return result;
 }

// #R001: Matchycore traceability implementation coverage.
 std::set<long long> ExtractMoneyCents(const std::string &text)
 { std::set<long long> cents;
  std::size_t p = 0;
  while (p < text.size())
  { std::size_t advance = 1;
   bool lookbehind_ok = p == 0 || !IsDigit(text[p - 1]);
   if (lookbehind_ok)
   { std::size_t q = p;
    if (text[q] == '$')
    { q += 1;
     while (q < text.size() && IsSpace(text[q])) q += 1;
    }
    if (q < text.size() && IsDigit(text[q]))
    { std::size_t end = MatchGroupedNumber(text, q);
     if (end == std::string::npos) end = MatchPlainNumber(text, q);
     if (end != std::string::npos)
     { std::string raw;
      for (std::size_t k = q; k < end; k += 1)
       if (text[k] != ',') raw.push_back(text[k]);
      std::optional<long long> value = DecimalToCents(raw);
      if (value.has_value()) cents.insert(*value);
      advance = end - p;
     }
    }
   }
   p += advance;
  }
  return cents;
 }

// #R001: Matchycore traceability implementation coverage.
 double AmountHintScore(const std::string &amount, const EmailCandidate &candidate)
 { std::string text = candidate.subject() + " " + candidate.preview() + " " + candidate.body_text();
  std::optional<long long> target_cents = DecimalToCents(amount);
  double score = 0.0;
  if (target_cents.has_value() && ExtractMoneyCents(text).count(*target_cents) > 0) score = 1.0;
  return score;
 }

// #R001: Matchycore traceability implementation coverage.
 double SenderHintScore(const std::string &transaction_text, const std::string &sender)
 { std::set<std::string> txn_tokens = LongTokens(transaction_text, 2), sender_tokens = LongTokens(sender, 2);
  double score = 0.0;
  if (!txn_tokens.empty() && !sender_tokens.empty())
   for (const std::string &token : txn_tokens)
    if (sender_tokens.count(token) > 0) score = 1.0;
  return score;
 }

// #R001: Matchycore traceability implementation coverage.
 double CompactMerchantHintScore(const std::string &transaction_text, const std::string &candidate_text)
 { std::string compact_candidate;
  for (char c : candidate_text)
  { unsigned char uc = static_cast<unsigned char>(c);
   if (uc >= 'A' && uc <= 'Z') compact_candidate.push_back(static_cast<char>(uc - 'A' + 'a'));
   else if ((uc >= 'a' && uc <= 'z') || IsDigit(c)) compact_candidate.push_back(c);
  }
  double score = 0.0;
  if (!compact_candidate.empty())
  { for (const std::string &token : SplitWhitespace(NormalizedText(transaction_text)))
   { bool eligible = token.size() >= 6 && token.find_first_not_of("0123456789") != std::string::npos;
    if (eligible && compact_candidate.find(token) != std::string::npos) score = 1.0;
   }
  }
  return score;
 }

// #R001: Matchycore traceability implementation coverage.
 double TimeProximityScore(TimePoint txn_time, TimePoint received_at)
 { double delta_seconds = std::abs(std::chrono::duration<double>(received_at - txn_time).count());
  double delta_hours = delta_seconds / 3600.0;
  double score = 0.1;
  if (delta_hours <= 6) score = 1.0;
  else if (delta_hours <= 24) score = 0.85;
  else if (delta_hours <= 72) score = 0.65;
  else if (delta_hours <= 24 * 30) score = 0.3;
  return score;
 }

// #R001: Matchycore traceability implementation coverage.
 std::vector<std::string> RelevanceTokens(const std::string &value)
 { std::vector<std::string> tokens;
  for (const std::string &part : SplitWhitespace(NormalizedText(value)))
   if (part.size() > 2) tokens.push_back(part);
  return tokens;
 }

// #R001: Matchycore traceability implementation coverage.
 std::map<std::string, int> DocumentFrequencies(const std::vector<std::string> &documents)
 { std::map<std::string, int> frequencies;
  for (const std::string &document : documents)
  { std::set<std::string> unique_tokens;
   for (const std::string &token : RelevanceTokens(document)) unique_tokens.insert(token);
   for (const std::string &token : unique_tokens) frequencies[token] += 1;
  }
  return frequencies;
 }

// #R001: Matchycore traceability implementation coverage.
 double InverseDocumentFrequency(int corpus_size, int document_frequency)
 { double numerator = corpus_size - document_frequency + 0.5;
  double denominator = document_frequency + 0.5;
  return std::log(1.0 + numerator / denominator);
 }

// #R001: Matchycore traceability implementation coverage.
 double Bm25Score(const std::string &query, const std::string &document, int corpus_size,
                  const std::map<std::string, int> &document_frequency_map, double average_document_length,
                  double k1, double b)
 { std::vector<std::string> document_tokens = RelevanceTokens(document);
  std::size_t document_length = document_tokens.size();
  std::map<std::string, int> term_counts;
  for (const std::string &token : document_tokens) term_counts[token] += 1;
  double length_norm = average_document_length > 0 ? average_document_length : 1.0;
  double score = 0.0;
  if (document_length > 0 && corpus_size > 0)
  { std::set<std::string> query_tokens;
   for (const std::string &token : RelevanceTokens(query)) query_tokens.insert(token);
   for (const std::string &query_token : query_tokens)
   { auto found = term_counts.find(query_token);
    int term_frequency = found == term_counts.end() ? 0 : found->second;
    if (term_frequency > 0)
    { auto df_found = document_frequency_map.find(query_token);
     int document_frequency = df_found == document_frequency_map.end() ? 0 : df_found->second;
     double idf = InverseDocumentFrequency(corpus_size, document_frequency);
     double denominator = term_frequency + k1 * (1.0 - b + b * (static_cast<double>(document_length) / length_norm));
     score += idf * (term_frequency * (k1 + 1.0)) / denominator;
    }
   }
  }
  return score;
 }

// #R001: Matchycore traceability implementation coverage.
 double Bm25Relevance(double score, double saturation)
 { double normalized = 0.0;
  if (score > 0.0 && saturation > 0.0) normalized = score / (score + saturation);
  return normalized;
 }

// #R001: Matchycore traceability implementation coverage.
 bool SubsetSumReachable(const std::vector<long long> &amounts_cents, long long target_cents,
                         long long tolerance_cents)
 { long long upper_bound = target_cents + tolerance_cents;
  long long lower_bound = target_cents - tolerance_cents;
  std::set<long long> reachable{0};
  for (long long amount : amounts_cents)
  { if (amount > 0)
   { std::set<long long> additions;
    for (long long partial : reachable)
     if (partial + amount <= upper_bound) additions.insert(partial + amount);
    reachable.insert(additions.begin(), additions.end());
   }
  }
  bool found = false;
  for (long long total : reachable)
   if (total != 0 && lower_bound <= total && total <= upper_bound) found = true;
  return found;
 }

// #R001: Matchycore traceability implementation coverage.
 double AmountReconciliationScore(const std::string &amount, const EmailCandidate &candidate, int max_terms)
 { std::string text = candidate.subject() + " " + candidate.preview() + " " + candidate.body_text();
  std::optional<long long> target_cents = DecimalToCents(amount);
  double score = 0.0;
  if (target_cents.has_value() && *target_cents > 0)
  { std::vector<long long> line_items;
   for (long long value : ExtractMoneyCents(text))
    if (value > 0 && value < *target_cents) line_items.push_back(value);
   std::sort(line_items.begin(), line_items.end());
   if (static_cast<int>(line_items.size()) > max_terms) line_items.resize(static_cast<std::size_t>(max_terms));
   if (SubsetSumReachable(line_items, *target_cents)) score = 1.0;
  }
  return score;
 }

// #R001: Matchycore traceability implementation coverage.
 double Round4(double value)
 { char buffer[64];
  std::snprintf(buffer, sizeof(buffer), "%.4f", value);
  return std::strtod(buffer, nullptr);
 }

// #R001: Matchycore traceability implementation coverage.
 std::vector<RankedCandidate> RankCandidates(const TransactionInput &transaction,
                                             const std::vector<EmailCandidate> &candidates,
                                             const std::set<std::string> &already_matched_ids)
 { std::vector<RankedCandidate> ranked;
  std::vector<std::string> corpus;
  corpus.reserve(candidates.size());
  for (const EmailCandidate &item : candidates)
   corpus.push_back(item.subject() + " " + item.preview() + " " + item.body_text());
  int corpus_size = static_cast<int>(corpus.size());
  std::map<std::string, int> document_frequency_map = DocumentFrequencies(corpus);
  std::size_t total_token_length = 0;
  for (const std::string &document : corpus) total_token_length += RelevanceTokens(document).size();
  double average_document_length = corpus_size > 0
   ? static_cast<double>(total_token_length) / static_cast<double>(corpus_size) : 0.0;
  std::string query_text = transaction.counterparty_name() + " " + transaction.description();
  for (std::size_t index = 0; index < candidates.size(); index += 1)
  { const EmailCandidate &item = candidates[index];
   const std::string &text_blob = corpus[index];
   std::string txn_blob = transaction.description() + " " + transaction.counterparty_name();
   const std::string &merchant_source =
    transaction.counterparty_name().empty() ? transaction.description() : transaction.counterparty_name();
   double merchant_overlap = TokenOverlap(merchant_source, text_blob);
   double description_overlap = TokenOverlap(transaction.description(), text_blob);
   double amount_score = AmountHintScore(transaction.amount(), item);
   double compact_merchant_score = CompactMerchantHintScore(txn_blob, text_blob);
   double sender_score = SenderHintScore(txn_blob, item.sender());
   double time_score = TimeProximityScore(transaction.date(), item.received_at());
   double bm25_relevance = Bm25Relevance(
    Bm25Score(query_text, text_blob, corpus_size, document_frequency_map, average_document_length));
   double reconciliation_score = AmountReconciliationScore(transaction.amount(), item);
   bool unmatched_priority = already_matched_ids.count(item.message_id()) == 0;
   double unmatched_bonus = unmatched_priority ? 0.15 : 0.0;
   double score = std::min(1.0,
    (merchant_overlap * 0.30) + (description_overlap * 0.20) + (amount_score * 0.15)
    + (compact_merchant_score * 0.20) + (sender_score * 0.10) + (time_score * 0.20)
    + (bm25_relevance * 0.25) + (reconciliation_score * 0.15) + unmatched_bonus);
   nlohmann::json reasons = {
    {"merchant_overlap", Round4(merchant_overlap)},
    {"description_overlap", Round4(description_overlap)},
    {"amount_hint", Round4(amount_score)},
    {"compact_merchant_hint", Round4(compact_merchant_score)},
    {"sender_hint", Round4(sender_score)},
    {"time_proximity", Round4(time_score)},
    {"bm25_relevance", Round4(bm25_relevance)},
    {"amount_reconciliation", Round4(reconciliation_score)},
    {"unmatched_email_priority", unmatched_priority}};
   ranked.emplace_back(item, score, std::move(reasons));
  }
  std::stable_sort(ranked.begin(), ranked.end(),
                   [](const RankedCandidate &a, const RankedCandidate &b) { return a.score() > b.score(); });
  return ranked;
 }
}
