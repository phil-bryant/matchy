#include "matchycore/search.hpp"
#include <map>
#include "matchycore/timeutil.hpp"

namespace matchycore::search
{ namespace
 { bool IsDigit(char c) { return c >= '0' && c <= '9'; }

  std::vector<std::string> NormalizedTokens(const std::string &source)
  { std::string normalized;
   normalized.reserve(source.size());
   for (char c : source)
   { unsigned char uc = static_cast<unsigned char>(c);
    if (uc >= 'A' && uc <= 'Z') normalized.push_back(static_cast<char>(uc - 'A' + 'a'));
    else if ((uc >= 'a' && uc <= 'z') || IsDigit(c)) normalized.push_back(c);
    else if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v') normalized.push_back(c);
    else normalized.push_back(' ');
   }
   std::vector<std::string> tokens;
   std::string current;
   for (char c : normalized)
   { if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v')
    { if (!current.empty()) tokens.push_back(current);
     current.clear();
    }
    else current.push_back(c);
   }
   if (!current.empty()) tokens.push_back(current);
   return tokens;
  }
 }

 std::vector<std::string> ExtractSearchTerms(const std::string &description, const std::string &counterparty_name,
                                             int max_terms)
 { std::vector<std::string> ordered_tokens;
  std::vector<std::string> sources{counterparty_name, description};
  for (const std::string &source : sources)
  { for (const std::string &token : NormalizedTokens(source))
   { bool eligible = static_cast<int>(ordered_tokens.size()) < max_terms && token.size() >= 4;
    if (eligible)
    { bool all_digits = token.find_first_not_of("0123456789") == std::string::npos;
     bool has_letter = token.find_first_of("abcdefghijklmnopqrstuvwxyz") != std::string::npos;
     bool seen = false;
     for (const std::string &existing : ordered_tokens)
      if (existing == token) seen = true;
     if (!all_digits && has_letter && !seen) ordered_tokens.push_back(token);
    }
   }
  }
  return ordered_tokens;
 }

 std::string DateWindowSuffix(TimePoint txn_date, int window_days)
 { std::string suffix;
  if (window_days > 0)
   suffix = " from:" + timeutil::UtcDateString(txn_date, -window_days)
    + " to:" + timeutil::UtcDateString(txn_date, window_days);
  return suffix;
 }

 std::vector<std::string> BuildScopedQueries(const std::vector<std::string> &terms, TimePoint txn_date,
                                             const std::vector<std::string> &fields, bool include_date_window,
                                             int window_days)
 { std::vector<std::string> scoped_queries;
  if (!terms.empty())
  { std::string date_window = include_date_window ? DateWindowSuffix(txn_date, window_days) : "";
   for (const std::string &term : terms)
    for (const std::string &field : fields) scoped_queries.push_back(field + ":" + term + date_window);
  }
  return scoped_queries;
 }

 std::vector<EmailCandidate> DedupeCandidates(const std::vector<EmailCandidate> &rows, std::size_t limit)
 { std::vector<EmailCandidate> deduped;
  std::map<std::string, bool> seen;
  for (const EmailCandidate &candidate : rows)
  { const std::string &message_id = candidate.message_id();
   bool accept = deduped.size() < limit && !message_id.empty() && seen.count(message_id) == 0;
   if (accept)
   { seen[message_id] = true;
    deduped.push_back(candidate);
   }
  }
  return deduped;
 }

 SearchEngine::SearchEngine(std::shared_ptr<mailcart::MailcartApi> client, const Settings &settings)
 : client_(std::move(client)),
   window_days_(settings.mailcart_search_date_window_days() != 0 ? settings.mailcart_search_date_window_days() : 45),
   cooldown_seconds_(settings.mailcart_failure_cooldown_seconds() != 0 ? settings.mailcart_failure_cooldown_seconds() : 15)
 { if (cooldown_seconds_ < 0) cooldown_seconds_ = 0;
 }

 bool SearchEngine::InCooldown() const
 { return std::chrono::steady_clock::now() < unavailable_until_;
 }

 void SearchEngine::MarkTemporarilyUnavailable()
 { if (cooldown_seconds_ > 0)
   unavailable_until_ = std::chrono::steady_clock::now() + std::chrono::seconds(cooldown_seconds_);
 }

 //R040: Timeouts skip just the query; connection/5xx failures arm the cooldown; 4xx propagate.
 std::vector<EmailCandidate> SearchEngine::SearchMailcart(const std::string &query,
                                                          const std::string &transaction_id, int limit)
 { std::vector<EmailCandidate> rows;
  (void)transaction_id;
  try
  { rows = client_->SearchCandidates(query, limit);
  }
  catch (const mailcart::MailcartError &exc)
  { bool transient = exc.kind() == mailcart::MailcartError::Kind::kConnection
    || (exc.kind() == mailcart::MailcartError::Kind::kHttp && exc.status() >= 500);
   if (exc.kind() == mailcart::MailcartError::Kind::kTimeout) rows.clear();
   else if (transient) MarkTemporarilyUnavailable();
   else throw;
  }
  return rows;
 }

 std::vector<EmailCandidate> SearchEngine::SearchCandidates(const TransactionInput &txn,
                                                            const std::string &transaction_id)
 { std::vector<EmailCandidate> result;
  if (!InCooldown())
  { std::vector<std::string> terms = ExtractSearchTerms(txn.description(), txn.counterparty_name());
   std::vector<std::string> query_plan = BuildScopedQueries(terms, txn.date(), {"body"}, true, window_days_);
   for (const std::string &query : BuildScopedQueries(terms, txn.date(), {"subject"}, true, window_days_))
    query_plan.push_back(query);
   for (const std::string &query : BuildScopedQueries(terms, txn.date(), {"body"}, false, window_days_))
    query_plan.push_back(query);
   query_plan.push_back("");
   bool done = false;
   for (std::size_t index = 0; !done && index < query_plan.size(); index += 1)
   { std::vector<EmailCandidate> rows = SearchMailcart(query_plan[index], transaction_id, 75);
    std::vector<EmailCandidate> candidates = DedupeCandidates(rows, 75);
    if (!candidates.empty())
    { result = candidates;
     done = true;
    }
    else if (InCooldown()) done = true;
   }
  }
  return result;
 }
}
