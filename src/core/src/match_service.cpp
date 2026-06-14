#include "matchycore/match_service.hpp"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <thread>
#include "matchycore/caching.hpp"
#include "matchycore/enrichment.hpp"
#include "matchycore/near_duplicate.hpp"
#include "matchycore/scoring.hpp"

namespace matchycore
{ namespace
// #R001: Matchycore traceability implementation coverage.
 { cldr::CldrCurrencyMatcher BuildMatcher(const Settings &settings)
  { return cldr::CldrCurrenciesCache(settings).CurrencyMatcher();
  }

// #R001: Matchycore traceability implementation coverage.
  std::shared_ptr<mailcart::MailcartApi> BuildClient(const Settings &settings)
  { auto client = std::make_shared<mailcart::MailcartClient>(settings);
   if (settings.mailcart_startup_healthcheck_enabled()) client->StartupPreflightHealthcheck();
   return client;
  }

  // Run `work` against the external session when provided, else inside a fresh unit of work
  // (commit-or-rollback per write_enabled), mirroring Python's _session_scope().
  template <typename Fn>
// #R001: Matchycore traceability implementation coverage.
  auto WithSession(const db::MatchRepository &repository, db::Session *external, Fn &&work)
  { if (external != nullptr) return work(*external);
   std::unique_ptr<db::Session> session = repository.OpenSession();
   auto result = work(*session);
   session->Complete();
   return result;
  }
 }

// #R001: Matchycore traceability implementation coverage.
 MatchService::MatchService(const Settings &settings)
 : settings_(settings), repository_(settings), mailcart_client_(BuildClient(settings)),
   search_engine_(mailcart_client_, settings), ai_ranker_(settings), cldr_matcher_(BuildMatcher(settings))
 {
 }

// #R001: Matchycore traceability implementation coverage.
 MatchService::MatchService(const Settings &settings, db::MatchRepository repository,
                            std::shared_ptr<mailcart::MailcartApi> mailcart_client,
                            std::shared_ptr<ai::AiTransport> ai_transport, cldr::CldrCurrencyMatcher cldr_matcher)
 : settings_(settings), repository_(std::move(repository)), mailcart_client_(std::move(mailcart_client)),
   search_engine_(mailcart_client_, settings), ai_ranker_(settings, std::move(ai_transport)),
   cldr_matcher_(std::move(cldr_matcher))
 {
 }

// #R001: Matchycore traceability implementation coverage.
 int MatchService::NearDuplicateMaxDistance() const
 { int raw = settings_.near_duplicate_max_hamming_distance();
  return raw > 0 ? raw : 0;
 }

// #R001: Matchycore traceability implementation coverage.
 void MatchService::MaybeMoveSelectedMessages(const std::vector<std::string> &selected_message_ids,
                                              const std::string &transaction_id, const std::string &source)
 { bool move_enabled = settings_.write_enabled() && settings_.email_move_enabled();
  if (move_enabled && mailcart_client_ != nullptr)
  { std::vector<std::string> unique_ids;
   for (const std::string &message_id : selected_message_ids)
   { bool seen = message_id.empty();
    for (const std::string &existing : unique_ids)
     if (existing == message_id) seen = true;
    if (!seen) unique_ids.push_back(message_id);
   }
   for (const std::string &message_id : unique_ids)
   { try
    { bool moved = mailcart_client_->MoveToMatchy(message_id);
     if (!moved)
      std::fprintf(stderr, "mailcart move_to_matchy returned false transaction_id=%s source=%s message_id=%s\n",
                   transaction_id.c_str(), source.c_str(), message_id.c_str());
    }
    catch (const std::exception &exc)
    { std::fprintf(stderr, "mailcart move_to_matchy failed transaction_id=%s source=%s message_id=%s error=%s\n",
                   transaction_id.c_str(), source.c_str(), message_id.c_str(), exc.what());
    }
   }
  }
 }

 nlohmann::json MatchService::MatchTransaction(const std::string &transaction_id, const std::string &trigger_source,
                                               bool force_rematch, db::Session *external_session,
                                               bool record_failure)
 { std::optional<TransactionInput> txn = WithSession(repository_, external_session,
   [&](db::Session &session) { return repository_.LoadTransaction(session, transaction_id); });
  if (!txn.has_value()) throw std::invalid_argument("Unknown transaction_id: " + transaction_id);
  std::vector<EmailCandidate> candidates = search_engine_.SearchCandidates(*txn, transaction_id);
  candidates = enrichment::EnrichCandidateBodies(mailcart_client_, settings_, candidates, transaction_id);
  candidates = enrichment::FilterCurrencyCandidates(cldr_matcher_, candidates);
  // #R001: Collapse near-duplicates after enrichment so similarity is judged on full bodies.
  candidates = near_duplicate::CollapseNearDuplicates(candidates, NearDuplicateMaxDistance());
  std::string planned_model = ai_ranker_.PlannedModelName();
  std::set<std::string> active_ids = WithSession(repository_, external_session,
   [&](db::Session &session) { return repository_.ListActiveEmailIdsForOtherTransactions(session, transaction_id); });
  std::vector<RankedCandidate> ranked = scoring::RankCandidates(*txn, candidates, active_ids);
  nlohmann::json current_rows = caching::RankedCandidateCacheRows(ranked);
  std::string current_hash = caching::CandidateSetHash(current_rows);
  std::vector<std::string> current_ids;
  for (const nlohmann::json &row : current_rows) current_ids.push_back(row["email_message_id"].get<std::string>());
  std::string current_message_id_hash = caching::CandidateMessageIdHash(current_ids);
  long long run_id = 0;
  std::optional<nlohmann::json> cached_response = WithSession(repository_, external_session,
   [&](db::Session &session) -> std::optional<nlohmann::json>
   { std::optional<nlohmann::json> cached = caching::MaybeCachedResponse(
     repository_, session, transaction_id, candidates.size(), planned_model, current_hash,
     current_message_id_hash, force_rematch);
    if (!cached.has_value())
     run_id = repository_.CreateRun(session, transaction_id, trigger_source, planned_model, ai::kPromptVersion);
    return cached;
   });
  nlohmann::json result;
  if (cached_response.has_value()) result = *cached_response;
  else
  { std::vector<std::string> selected_ids;
   std::optional<AiSelection> ai_selection;
   try
   { ai_selection = ai_ranker_.Select(*txn, ranked);
    selected_ids = WithSession(repository_, external_session,
     [&](db::Session &session)
     { repository_.UpdateRunModelName(session, run_id, ai_selection->model_name());
      std::set<std::string> ai_selected(ai_selection->selected_message_ids().begin(),
                                        ai_selection->selected_message_ids().end());
      repository_.InsertCandidates(session, run_id, transaction_id, ranked, ai_selected);
      return repository_.PersistAiResult(session, transaction_id, run_id, ranked, *ai_selection,
                                         settings_.auto_confirm_threshold());
     });
    MaybeMoveSelectedMessages(selected_ids, transaction_id, "ai");
   }
   catch (const std::exception &exc)
   { // #R001: Persist the failure on a fresh session so the next driver loop retries this transaction.
    if (record_failure && run_id != 0)
    { try
     { if (external_session == nullptr)
      { std::unique_ptr<db::Session> failed_session = repository_.OpenSession();
       repository_.MarkRunFailed(*failed_session, run_id, exc.what());
       failed_session->Complete();
      }
      else repository_.MarkRunFailed(*external_session, run_id, exc.what());
     }
     catch (const std::exception &mark_exc)
     { std::fprintf(stderr, "matchy failed to persist failed run run_id=%lld error=%s\n", run_id, mark_exc.what());
     }
    }
    throw;
   }
   result = nlohmann::json{
    {"transaction_id", transaction_id},
    {"run_id", run_id},
    {"selected_message_ids", selected_ids},
    {"candidate_count", candidates.size()},
    {"ai_confidence", ai_selection->confidence()},
    {"uncertain", ai_selection->uncertain()},
    {"skipped", false}};
  }
  return result;
 }

// #R001: Matchycore traceability implementation coverage.
 std::vector<nlohmann::json> MatchService::MatchTransactionsAtomic(const std::vector<std::string> &transaction_ids,
                                                                   const std::string &trigger_source,
                                                                   bool force_rematch)
 { std::vector<nlohmann::json> rows;
  std::unique_ptr<db::Session> session = repository_.OpenSession();
  for (const std::string &transaction_id : transaction_ids)
   rows.push_back(MatchTransaction(transaction_id, trigger_source, force_rematch, session.get(), false));
  session->Complete();
  return rows;
 }

// #R001: Matchycore traceability implementation coverage.
 std::vector<nlohmann::json> MatchService::MatchPendingTransactions(int limit, int lookback_days,
                                                                    const std::string &trigger_source,
                                                                    bool force_rematch)
 { std::vector<std::string> transaction_ids = WithSession(repository_, nullptr,
   [&](db::Session &session) { return repository_.ListPendingTransactionIds(session, limit, lookback_days); });
  const char *raw_workers = std::getenv("MATCHY_PENDING_MAX_WORKERS");
  int max_workers = 4;
  if (raw_workers != nullptr)
  { char *end = nullptr;
   long parsed = std::strtol(raw_workers, &end, 10);
   if (end != raw_workers && *end == '\0' && parsed >= 1) max_workers = static_cast<int>(parsed);
  }
  if (!transaction_ids.empty()) max_workers = std::min<int>(max_workers, static_cast<int>(transaction_ids.size()));
  if (max_workers < 1) max_workers = 1;
  std::vector<nlohmann::json> results(transaction_ids.size());
  if (!transaction_ids.empty())
  { std::atomic<std::size_t> next_index{0};
   std::vector<std::thread> workers;
   for (int w = 0; w < max_workers; w += 1)
   { workers.emplace_back([&]()
    { bool working = true;
     while (working)
     { std::size_t index = next_index.fetch_add(1);
      if (index >= transaction_ids.size()) working = false;
      else
      { const std::string &transaction_id = transaction_ids[index];
       try
       { results[index] = MatchTransaction(transaction_id, trigger_source, force_rematch);
       }
       catch (const std::exception &exc)
       { std::fprintf(stderr, "matchy batch entry failed transaction_id=%s error=%s\n",
                      transaction_id.c_str(), exc.what());
        results[index] = nlohmann::json{
         {"transaction_id", transaction_id},
         {"run_id", nullptr},
         {"selected_message_ids", nlohmann::json::array()},
         {"candidate_count", 0},
         {"ai_confidence", 0.0},
         {"uncertain", true},
         {"skipped", false},
         {"error", exc.what()}};
       }
      }
     }
    });
   }
   for (std::thread &worker : workers) worker.join();
  }
  return results;
 }

 nlohmann::json MatchService::ConfirmMatch(const std::string &transaction_id, const std::string &email_message_id,
                                           const std::optional<std::string> &note)
 { long long match_id = 0;
  try
  { std::unique_ptr<db::Session> session = repository_.OpenSession();
   repository_.DeactivateActiveMatch(*session, transaction_id);
   match_id = repository_.InsertHumanConfirmedMatch(*session, transaction_id, email_message_id, note);
   session->Complete();
  }
  catch (const std::runtime_error &exc)
  { // #R001: Foreign-key violations on client-supplied ids surface as a domain error (HTTP 404).
   std::string detail = exc.what();
   bool integrity = detail.find("constraint") != std::string::npos
    || detail.find("CONSTRAINT") != std::string::npos || detail.find("violates") != std::string::npos
    || detail.find("FOREIGN KEY") != std::string::npos;
   if (integrity)
    throw std::invalid_argument("Unknown transaction_id or email_message_id for confirmation: "
                                + transaction_id + "/" + email_message_id);
   throw;
  }
  MaybeMoveSelectedMessages({email_message_id}, transaction_id, "human_confirm");
  return nlohmann::json{{"status", "confirmed"}, {"match_id", match_id}};
 }
}
