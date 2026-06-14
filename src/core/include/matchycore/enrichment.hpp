#pragma once
#include <memory>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/cldr.hpp"
#include "matchycore/mailcart.hpp"
#include "matchycore/models.hpp"
#include "matchycore/settings.hpp"

// Port of matchy/enrichment.py (Mailcart body enrichment + CLDR currency scoping).
namespace matchycore::enrichment
{ // #R001: Prefer text_body, then html_body, then body_text from a message payload.
 std::string EnrichmentBodyText(const nlohmann::json &payload);

 // #R001: Replace candidate bodies with full Mailcart bodies (bounded concurrency, per-candidate fault
 // #R001: tolerance, overall deadline). Returns candidates unchanged when enrichment is disabled.
 std::vector<EmailCandidate> EnrichCandidateBodies(const std::shared_ptr<mailcart::MailcartApi> &client,
                                                   const Settings &settings,
                                                   const std::vector<EmailCandidate> &candidates,
                                                   const std::string &transaction_id);

 // #R001: Scope matchable candidates to messages containing a standalone CLDR currency code or symbol;
 // #R001: a matcher without tokens leaves candidates unfiltered.
 std::vector<EmailCandidate> FilterCurrencyCandidates(const cldr::CldrCurrencyMatcher &matcher,
                                                      const std::vector<EmailCandidate> &candidates);
}
