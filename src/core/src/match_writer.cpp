#include <chrono>
#include "matchycore/repository.hpp"
#include "matchycore/timeutil.hpp"

// Port of matchy/match_writer.py: candidate inserts plus AI/human match persistence.
namespace matchycore::db
{ namespace
 { using tellercore::db::Params;
  using tellercore::db::Value;

  Value OptionalText(const std::string &text)
  { return text.empty() ? Value(std::monostate{}) : Value(text);
  }
 }

 void MatchRepository::InsertCandidates(Session &session, long long match_run_id, const std::string &transaction_id,
                                        const std::vector<RankedCandidate> &candidates,
                                        const std::set<std::string> &ai_selected_ids) const
 { std::string insert_sql = Sql(R"sql(
   INSERT INTO matchy.transaction_email_candidate (
       match_run_id,
       transaction_id,
       email_message_id,
       email_received_at,
       score,
       reason_json,
       is_unmatched_email_priority,
       is_selected_by_ai,
       cached_subject,
       cached_sender,
       cached_snippet,
       cached_fetched_at
   ) VALUES (
       :match_run_id,
       :transaction_id,
       :email_message_id,
       :email_received_at,
       :score,
       )sql" + JsonbParam("reason_json", is_sqlite_) + R"sql(,
       :is_unmatched_email_priority,
       :is_selected_by_ai,
       :cached_subject,
       :cached_sender,
       :cached_snippet,
       CASE WHEN :cached_subject IS NULL AND :cached_sender IS NULL AND :cached_snippet IS NULL
            THEN NULL ELSE CURRENT_TIMESTAMP END
   ))sql");
  for (const RankedCandidate &ranked : candidates)
  { //R680: preview falls back to the first 240 body characters when the body exists.
   const EmailCandidate &candidate = ranked.candidate();
   std::string preview = candidate.body_text().empty() ? candidate.preview()
    : (candidate.preview().empty() ? candidate.body_text().substr(0, 240) : candidate.preview());
   bool unmatched_priority = ranked.reasons().value("unmatched_email_priority", false);
   Params params{
    {"match_run_id", Value(static_cast<int64_t>(match_run_id))},
    {"transaction_id", Value(transaction_id)},
    {"email_message_id", Value(candidate.message_id())},
    {"email_received_at", BindTimestamp(candidate.received_at(), is_sqlite_)},
    {"score", Value(ranked.score())},
    {"reason_json", Value(ranked.reasons().dump())},
    {"is_unmatched_email_priority", Value(static_cast<int64_t>(unmatched_priority ? 1 : 0))},
    {"is_selected_by_ai", Value(static_cast<int64_t>(ai_selected_ids.count(candidate.message_id()) > 0 ? 1 : 0))},
    {"cached_subject", OptionalText(candidate.subject())},
    {"cached_sender", OptionalText(candidate.sender())},
    {"cached_snippet", OptionalText(preview)}};
   session.db().execute(insert_sql, params);
  }
 }

 bool MatchRepository::HasActiveMatch(Session &session, const std::string &email_message_id) const
 { std::optional<tellercore::db::Row> row = session.db().query_one(Sql(R"sql(
   SELECT 1 AS present
     FROM matchy.transaction_email_match
    WHERE email_message_id = :email_message_id
      AND active = TRUE
    LIMIT 1)sql"), Params{{"email_message_id", Value(email_message_id)}});
  return row.has_value();
 }

 std::vector<std::string> MatchRepository::PersistAiResult(Session &session, const std::string &transaction_id,
                                                           long long run_id,
                                                           const std::vector<RankedCandidate> &ranked_candidates,
                                                           const AiSelection &ai_selection,
                                                           double auto_confirm_threshold) const
 { std::vector<std::string> selected;
  TimePoint now = std::chrono::system_clock::now();
  std::set<std::string> candidate_message_ids;
  for (const RankedCandidate &ranked : ranked_candidates) candidate_message_ids.insert(ranked.candidate().message_id());
  std::set<std::string> selected_ids;
  for (const std::string &id : ai_selection.selected_message_ids())
   if (candidate_message_ids.count(id) > 0) selected_ids.insert(id);
  bool conflict_detected = false;
  session.db().execute(Sql(R"sql(
   UPDATE matchy.transaction_email_match
      SET active = FALSE,
          updated_at = CURRENT_TIMESTAMP
    WHERE transaction_id = :transaction_id
      AND active = TRUE)sql"), Params{{"transaction_id", Value(transaction_id)}});
  std::string match_insert_sql = Sql(R"sql(
   INSERT INTO matchy.transaction_email_match (
       transaction_id,
       email_message_id,
       state,
       ai_confidence,
       explanation_json,
       selected_by,
       selected_at,
       active
   ) VALUES (
       :transaction_id,
       :email_message_id,
       :state,
       :ai_confidence,
       )sql" + JsonbParam("explanation_json", is_sqlite_) + R"sql(,
       'ai',
       :selected_at,
       TRUE
   ))sql");
  if (ranked_candidates.empty() || selected_ids.empty())
  { nlohmann::json explanation{{"rationale", ai_selection.rationale()}, {"run_id", run_id}};
   session.db().execute(match_insert_sql, Params{
    {"transaction_id", Value(transaction_id)},
    {"email_message_id", Value(std::monostate{})},
    {"state", Value(std::string("ai_no_match_found"))},
    {"ai_confidence", Value(ai_selection.confidence())},
    {"explanation_json", Value(explanation.dump())},
    {"selected_at", BindTimestamp(now, is_sqlite_)}});
   UpdateRunStatus(session, run_id, "no_candidates", std::nullopt);
  }
  else
  { std::string state = "ai_candidate_uncertain";
   if (ai_selection.confidence() >= auto_confirm_threshold && !ai_selection.uncertain())
    state = "ai_match_confident";
   for (const RankedCandidate &ranked : ranked_candidates)
   { const std::string &message_id = ranked.candidate().message_id();
    if (selected_ids.count(message_id) > 0)
    { if (HasActiveMatch(session, message_id))
     { state = "ai_candidate_uncertain";
      conflict_detected = true;
     }
     else
     { nlohmann::json explanation{{"rationale", ai_selection.rationale()},
                                  {"deterministic_reasons", ranked.reasons()}, {"run_id", run_id}};
      session.db().execute(match_insert_sql, Params{
       {"transaction_id", Value(transaction_id)},
       {"email_message_id", Value(message_id)},
       {"state", Value(state)},
       {"ai_confidence", Value(ai_selection.confidence())},
       {"explanation_json", Value(explanation.dump())},
       {"selected_at", BindTimestamp(now, is_sqlite_)}});
      selected.push_back(message_id);
     }
    }
   }
   if (conflict_detected && selected.empty())
   { nlohmann::json explanation{{"rationale", ai_selection.rationale()}, {"run_id", run_id},
                                {"reason", "selected_email_already_has_active_match"}};
    session.db().execute(match_insert_sql, Params{
     {"transaction_id", Value(transaction_id)},
     {"email_message_id", Value(std::monostate{})},
     {"state", Value(std::string("ai_candidate_uncertain"))},
     {"ai_confidence", Value(ai_selection.confidence())},
     {"explanation_json", Value(explanation.dump())},
     {"selected_at", BindTimestamp(now, is_sqlite_)}});
    state = "ai_candidate_uncertain";
   }
   UpdateRunStatus(session, run_id, state == "ai_candidate_uncertain" ? "needs_review" : "succeeded", std::nullopt);
  }
  return selected;
 }

 void MatchRepository::DeactivateActiveMatch(Session &session, const std::string &transaction_id) const
 { session.db().execute(Sql(R"sql(
   UPDATE matchy.transaction_email_match
      SET active = FALSE, updated_at = CURRENT_TIMESTAMP
    WHERE transaction_id = :transaction_id AND active = TRUE)sql"),
   Params{{"transaction_id", Value(transaction_id)}});
 }

 long long MatchRepository::InsertHumanConfirmedMatch(Session &session, const std::string &transaction_id,
                                                      const std::string &email_message_id,
                                                      const std::optional<std::string> &note) const
 { TimePoint now = std::chrono::system_clock::now();
  nlohmann::json explanation = nlohmann::json::object();
  if (note.has_value() && !note->empty()) explanation["note"] = *note;
  std::string insert_sql = R"sql(
   INSERT INTO matchy.transaction_email_match (
       transaction_id, email_message_id, state, selected_by, selected_at, active, explanation_json
   ) VALUES (
       :transaction_id, :email_message_id, 'human_confirmed_ai_match', 'human', :selected_at, TRUE, )sql"
   + JsonbParam("explanation", is_sqlite_) + R"sql(
   ))sql";
  Params params{
   {"transaction_id", Value(transaction_id)},
   {"email_message_id", Value(email_message_id)},
   {"selected_at", BindTimestamp(now, is_sqlite_)},
   {"explanation", Value(explanation.dump())}};
  return LastInsertId(session, "match_id", insert_sql, params);
 }
}
