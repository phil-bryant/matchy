#include "matchycore/enrichment.hpp"
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <map>
#include <mutex>
#include <thread>

namespace matchycore::enrichment
{ namespace
// #R001: Matchycore traceability implementation coverage.
 { std::string Strip(const std::string &value)
  { std::size_t begin = value.find_first_not_of(" \t\n\r\f\v");
   std::string out;
   if (begin != std::string::npos) out = value.substr(begin, value.find_last_not_of(" \t\n\r\f\v") - begin + 1);
   return out;
  }

// #R001: Matchycore traceability implementation coverage.
  std::string PayloadString(const nlohmann::json &payload, const std::string &key)
  { std::string value;
   if (payload.is_object() && payload.contains(key) && payload[key].is_string()) value = payload[key].get<std::string>();
   return value;
  }

  // Shared state for the bounded fetch pool; abandoned threads keep it (and the client) alive.
  class FetchState
  { public:
   std::mutex mutex;
   std::condition_variable cv;
   std::map<std::string, nlohmann::json> payload_by_id;
   std::vector<std::string> message_ids;
   std::size_t next_index = 0;
   std::size_t completed = 0;
   std::shared_ptr<mailcart::MailcartApi> client;
   int per_message_timeout = 0;
  };
 }

// #R001: Matchycore traceability implementation coverage.
 std::string EnrichmentBodyText(const nlohmann::json &payload)
 { std::string body_text = Strip(PayloadString(payload, "text_body"));
  if (body_text.empty()) body_text = Strip(PayloadString(payload, "html_body"));
  if (body_text.empty()) body_text = Strip(PayloadString(payload, "body_text"));
  return body_text;
 }

 std::vector<EmailCandidate> EnrichCandidateBodies(const std::shared_ptr<mailcart::MailcartApi> &client,
                                                   const Settings &settings,
                                                   const std::vector<EmailCandidate> &candidates,
                                                   const std::string &transaction_id)
 { std::vector<EmailCandidate> result = candidates;
  bool enabled = settings.mailcart_body_enrichment_enabled() && !candidates.empty() && client != nullptr;
  if (enabled)
  { int limit = settings.mailcart_body_enrichment_limit() != 0 ? settings.mailcart_body_enrichment_limit() : 75;
   int timeout_seconds = std::max(1, settings.mailcart_body_enrichment_timeout_seconds() != 0
    ? settings.mailcart_body_enrichment_timeout_seconds() : 25);
   int max_workers = std::max(1, settings.mailcart_body_enrichment_max_workers() != 0
    ? settings.mailcart_body_enrichment_max_workers() : 8);
   int per_message_timeout = std::max(1, settings.mailcart_get_message_timeout_seconds() != 0
    ? settings.mailcart_get_message_timeout_seconds() : 6);
   std::size_t enrich_count = std::min(candidates.size(), static_cast<std::size_t>(std::max(1, limit)));
   // #R001: Preserve first-seen ordering while deduplicating ids within the enrichment window.
   auto state = std::make_shared<FetchState>();
   state->client = client;
   state->per_message_timeout = per_message_timeout;
   for (std::size_t index = 0; index < enrich_count; index += 1)
   { const std::string &message_id = candidates[index].message_id();
    bool seen = false;
    for (const std::string &existing : state->message_ids)
     if (existing == message_id) seen = true;
    if (!seen) state->message_ids.push_back(message_id);
   }
   // #R001: Fetch payloads concurrently, tolerating per-message failures and the overall deadline.
   std::size_t worker_count = std::min<std::size_t>(static_cast<std::size_t>(max_workers), state->message_ids.size());
   for (std::size_t w = 0; w < worker_count; w += 1)
   { std::thread([state, transaction_id]()
    { bool working = true;
     while (working)
     { std::string message_id;
      { std::lock_guard<std::mutex> lock(state->mutex);
       if (state->next_index < state->message_ids.size())
       { message_id = state->message_ids[state->next_index];
        state->next_index += 1;
       }
       else working = false;
      }
      if (working)
      { nlohmann::json payload = nlohmann::json::object();
       try
       { payload = state->client->GetMessage(message_id, state->per_message_timeout);
       }
       catch (const std::exception &exc)
       { std::fprintf(stderr, "mailcart get_message failed message_id=%s transaction_id=%s error=%s\n",
                      message_id.c_str(), transaction_id.c_str(), exc.what());
       }
       std::lock_guard<std::mutex> lock(state->mutex);
       state->payload_by_id[message_id] = payload;
       state->completed += 1;
       state->cv.notify_all();
      }
     }
    }).detach();
   }
   std::map<std::string, nlohmann::json> payload_by_id;
   { std::unique_lock<std::mutex> lock(state->mutex);
    bool finished = state->cv.wait_for(lock, std::chrono::seconds(timeout_seconds),
                                       [&state]() { return state->completed >= state->message_ids.size(); });
    if (!finished)
     std::fprintf(stderr, "mailcart body enrichment timed out transaction_id=%s unresolved_candidates=%zu timeout_seconds=%d\n",
                  transaction_id.c_str(), state->message_ids.size() - state->completed, timeout_seconds);
    payload_by_id = state->payload_by_id;
   }
   // #R001: Apply enriched payloads to the configured candidate prefix, leaving unmatched rows unchanged.
   std::vector<EmailCandidate> enriched;
   for (std::size_t index = 0; index < enrich_count; index += 1)
   { const EmailCandidate &candidate = candidates[index];
    nlohmann::json payload = nlohmann::json::object();
    auto found = payload_by_id.find(candidate.message_id());
    if (found != payload_by_id.end()) payload = found->second;
    std::string body_text = EnrichmentBodyText(payload);
    if (!body_text.empty())
     enriched.emplace_back(candidate.message_id(),
                           candidate.subject().empty() ? PayloadString(payload, "subject") : candidate.subject(),
                           candidate.preview().empty() ? PayloadString(payload, "preview") : candidate.preview(),
                           candidate.received_at(),
                           candidate.sender().empty() ? PayloadString(payload, "sender") : candidate.sender(),
                           body_text);
    else enriched.push_back(candidate);
   }
   for (std::size_t index = enrich_count; index < candidates.size(); index += 1) enriched.push_back(candidates[index]);
   result = enriched;
  }
  return result;
 }

// #R001: Matchycore traceability implementation coverage.
 std::vector<EmailCandidate> FilterCurrencyCandidates(const cldr::CldrCurrencyMatcher &matcher,
                                                      const std::vector<EmailCandidate> &candidates)
 { std::vector<EmailCandidate> filtered = candidates;
  if (!candidates.empty() && !matcher.tokens().empty())
  { filtered.clear();
   for (const EmailCandidate &candidate : candidates)
   { std::string text_blob = candidate.subject() + " " + candidate.preview() + " " + candidate.body_text();
    if (matcher.ContainsStandaloneCurrency(text_blob)) filtered.push_back(candidate);
   }
  }
  return filtered;
 }
}
