#include "matchycore/repository.hpp"
#include <cstdlib>
#include <ctime>
#include <regex>
#include "matchycore/timeutil.hpp"

namespace matchycore::db
{ namespace
 { using tellercore::db::Params;
  using tellercore::db::Row;
  using tellercore::db::Value;

  std::string RowText(const Row &row, const std::string &name)
  { std::optional<std::string> text = row.get_text(name);
   std::string out;
   if (text.has_value()) out = *text;
   else
   { std::optional<long long> integer = row.get_int(name);
    if (integer.has_value()) out = std::to_string(*integer);
   }
   return out;
  }

  double RowDouble(const Row &row, const std::string &name)
  { std::optional<double> direct = row.get_double(name);
   double out = 0.0;
   if (direct.has_value()) out = *direct;
   else
   { std::optional<std::string> text = row.get_text(name);
    if (text.has_value()) out = std::strtod(text->c_str(), nullptr);
   }
   return out;
  }

  //R720: SQLite stores money as integer cents; render the exact Decimal(cents)/100 string Python produces.
  std::string CentsToDecimalString(long long cents)
  { bool negative = cents < 0;
   unsigned long long magnitude = negative ? static_cast<unsigned long long>(-(cents + 1)) + 1
    : static_cast<unsigned long long>(cents);
   unsigned long long whole = magnitude / 100, fraction = magnitude % 100;
   std::string out = (negative && magnitude > 0 ? "-" : "") + std::to_string(whole);
   if (fraction != 0)
   { char buffer[8];
    std::snprintf(buffer, sizeof(buffer), "%02llu", fraction);
    std::string digits(buffer);
    while (!digits.empty() && digits.back() == '0') digits.pop_back();
    out += "." + digits;
   }
   return out;
  }

  //R015: JSON candidate metadata arrives parsed (jsonb text) on PostgreSQL and as text on SQLite.
  nlohmann::json ParsedReasonJson(const Row &row)
  { nlohmann::json out = nlohmann::json::object();
   std::optional<std::string> raw = row.get_text("reason_json");
   if (raw.has_value() && !raw->empty())
   { nlohmann::json parsed = nlohmann::json::parse(*raw, nullptr, false);
    if (!parsed.is_discarded() && parsed.is_object()) out = parsed;
   }
   return out;
  }
 }

 std::string SqlForTarget(const std::string &sql_text, bool is_sqlite)
 { std::string out = sql_text;
  if (is_sqlite)
  { static const std::regex owned_re("\\b(classy|matchy)\\.([A-Za-z_][A-Za-z0-9_]*)\\b");
   out = std::regex_replace(out, owned_re, "teller.$1_$2");
   static const std::regex txn_re("\\bteller\\.transaction\\b");
   out = std::regex_replace(out, txn_re, "teller.\"transaction\"");
  }
  return out;
 }

 std::string JsonbParam(const std::string &param_name, bool is_sqlite)
 { return is_sqlite ? ":" + param_name : "CAST(:" + param_name + " AS jsonb)";
 }

 tellercore::db::Value BindTimestamp(TimePoint value, bool is_sqlite)
 { std::string iso = timeutil::FormatIsoNaive(value);
  std::string out;
  if (is_sqlite)
  { out = iso.substr(0, 19);
   std::size_t t_pos = out.find('T');
   if (t_pos != std::string::npos) out[t_pos] = ' ';
  }
  else out = timeutil::FormatIsoUtc(value);
  return tellercore::db::Value(out);
 }

 std::string DbDatetime::Iso() const
 { return had_offset_ ? timeutil::FormatIsoUtc(value_) : timeutil::FormatIsoNaive(value_);
 }

 std::optional<DbDatetime> AsDatetime(const tellercore::db::Value &value)
 { std::optional<DbDatetime> result;
  std::string text;
  if (std::holds_alternative<std::string>(value)) text = std::get<std::string>(value);
  else if (std::holds_alternative<int64_t>(value)) text = std::to_string(std::get<int64_t>(value));
  std::size_t begin = text.find_first_not_of(" \t\n\r");
  if (begin != std::string::npos)
  { text = text.substr(begin, text.find_last_not_of(" \t\n\r") - begin + 1);
   // Postgres timestamptz text ends in "+HH" or "+HH:MM"; Python received tz-aware datetimes there.
   bool had_offset = false;
   static const std::regex offset_re("([+-][0-9]{2})(:?[0-9]{2})?$");
   std::smatch match;
   std::string normalized = text;
   if (normalized.size() > 10 && std::regex_search(normalized, match, offset_re))
   { had_offset = true;
    std::string suffix = match[1].str() + (match[2].matched && match[2].str()[0] == ':' ? match[2].str()
     : (match[2].matched ? ":" + match[2].str() : ":00"));
    normalized = normalized.substr(0, normalized.size() - match[0].length()) + suffix;
   }
   std::size_t t_pos = normalized.find(' ');
   if (t_pos != std::string::npos) normalized[t_pos] = 'T';
   std::optional<TimePoint> parsed = timeutil::ParseIso8601(normalized);
   if (parsed.has_value()) result = DbDatetime(*parsed, had_offset);
  }
  return result;
 }

 Session::Session(std::unique_ptr<tellercore::db::Db> db, bool write_enabled)
 : db_(std::move(db)), write_enabled_(write_enabled)
 { db_->begin();
 }

 Session::~Session()
 { if (!finished_ && db_ != nullptr)
  { try
   { db_->rollback();
   }
   catch (...)
   { // Destructor must not throw; the connection is being discarded anyway.
   }
  }
 }

 void Session::Complete()
 { if (!finished_)
  { if (write_enabled_) db_->commit();
   else db_->rollback();
   finished_ = true;
  }
 }

 void Session::Abort()
 { if (!finished_)
  { db_->rollback();
   finished_ = true;
  }
 }

 MatchRepository::MatchRepository(const Settings &settings)
 : MatchRepository(settings, [] {
    //R001: Default the TELLER_DB_ROLE override off; matchy writes matchy.* as the profile's base user.
    if (std::getenv("TELLER_DB_ROLE") == nullptr) ::setenv("TELLER_DB_ROLE", "", 0);
    return tellercore::resolve_profile();
   }())
 {
 }

 MatchRepository::MatchRepository(const Settings &settings, tellercore::DbProfile profile)
 : profile_(std::move(profile)), write_enabled_(settings.write_enabled()),
   is_sqlite_(profile_.target == tellercore::DbTarget::kSqlite)
 {
 }

 std::unique_ptr<Session> MatchRepository::OpenSession() const
 { return std::make_unique<Session>(tellercore::db::open_from_profile(profile_), write_enabled_);
 }

 std::optional<TransactionInput> MatchRepository::LoadTransaction(Session &session,
                                                                  const std::string &transaction_id) const
 { std::optional<TransactionInput> result;
  std::optional<Row> row = session.db().query_one(Sql(R"sql(
   SELECT tt.transaction_id,
          tt.account_id,
          tt.amount,
          tt.date AS date_value,
          tt.description,
          COALESCE(tdc.name, '') AS counterparty_name
     FROM teller.transaction tt
LEFT JOIN teller.transaction_details td
       ON td.transaction_details_id = tt.transaction_details_id
LEFT JOIN teller.transaction_details_counterparty tdc
       ON tdc.transaction_details_counterparty_id = td.transaction_details_counterparty_id
    WHERE tt.transaction_id = :transaction_id
    LIMIT 1)sql"), Params{{"transaction_id", Value(transaction_id)}});
  if (row.has_value())
  { std::string amount;
   if (is_sqlite_)
   { std::optional<long long> cents = row->get_int("amount");
    amount = CentsToDecimalString(cents.has_value() ? *cents : 0);
   }
   else amount = RowText(*row, "amount");
   std::optional<DbDatetime> date_ts = AsDatetime(row->columns.at("date_value"));
   if (date_ts.has_value())
    result = TransactionInput(RowText(*row, "transaction_id"), RowText(*row, "account_id"), amount,
                              date_ts->value(), RowText(*row, "description"), RowText(*row, "counterparty_name"));
  }
  return result;
 }

 long long MatchRepository::LastInsertId(Session &session, const std::string &id_column,
                                         const std::string &insert_sql, const tellercore::db::Params &params) const
 { long long id = 0;
  if (is_sqlite_)
  { //R721 R700: pysqlcipher3 cannot surface INSERT..RETURNING rows; use last_insert_rowid().
   session.db().execute(Sql(insert_sql), params);
   std::optional<Row> row = session.db().query_one("SELECT last_insert_rowid() AS id");
   if (row.has_value() && row->get_int("id").has_value()) id = *row->get_int("id");
  }
  else
  { std::optional<Row> row = session.db().query_one(Sql(insert_sql + " RETURNING " + id_column), params);
   if (row.has_value() && row->get_int(id_column).has_value()) id = *row->get_int(id_column);
  }
  return id;
 }

 long long MatchRepository::CreateRun(Session &session, const std::string &transaction_id,
                                      const std::string &trigger_source, const std::string &model_name,
                                      const std::string &prompt_version) const
 { Params params{{"transaction_id", Value(transaction_id)}, {"trigger_source", Value(trigger_source)},
                 {"model_name", Value(model_name)}, {"prompt_version", Value(prompt_version)}};
  std::string insert_sql = R"sql(
   INSERT INTO matchy.transaction_email_match_run (
       transaction_id, trigger_source, model_name, prompt_version, status
   ) VALUES (
       :transaction_id, :trigger_source, :model_name, :prompt_version, 'needs_review'
   ))sql";
  return LastInsertId(session, "match_run_id", insert_sql, params);
 }

 void MatchRepository::UpdateRunModelName(Session &session, long long run_id, const std::string &model_name) const
 { session.db().execute(Sql(R"sql(
   UPDATE matchy.transaction_email_match_run
      SET model_name = :model_name
    WHERE match_run_id = :match_run_id)sql"),
   Params{{"model_name", Value(model_name)}, {"match_run_id", Value(static_cast<int64_t>(run_id))}});
 }

 std::vector<std::string> MatchRepository::ListPendingTransactionIds(Session &session, int limit,
                                                                     int lookback_days) const
 { std::time_t now = std::time(nullptr);
  std::tm local{};
  localtime_r(&now, &local);
  std::tm cutoff = local;
  cutoff.tm_mday -= lookback_days;
  std::mktime(&cutoff);
  char cutoff_date[16];
  std::snprintf(cutoff_date, sizeof(cutoff_date), "%04d-%02d-%02d",
                cutoff.tm_year + 1900, cutoff.tm_mon + 1, cutoff.tm_mday);
  std::vector<Row> rows = session.db().query(Sql(R"sql(
   WITH latest_runs AS (
       SELECT transaction_id, created_at, completed_at
         FROM (
           SELECT temr.transaction_id,
                  temr.created_at,
                  temr.completed_at,
                  ROW_NUMBER() OVER (
                      PARTITION BY temr.transaction_id
                      ORDER BY temr.match_run_id DESC
                  ) AS rn
             FROM matchy.transaction_email_match_run temr
         ) ranked
        WHERE ranked.rn = 1
   )
   SELECT tt.transaction_id
     FROM teller.transaction tt
LEFT JOIN matchy.transaction_email_match tem
       ON tem.transaction_id = tt.transaction_id
      AND tem.active = TRUE
LEFT JOIN latest_runs lr
       ON lr.transaction_id = tt.transaction_id
    WHERE (
          tt.date >= :cutoff_date
       OR lr.transaction_id IS NULL
    )
      AND (
          tem.match_id IS NULL
          OR CAST(tem.state AS TEXT) = 'ai_candidate_uncertain'
          OR (CAST(tem.state AS TEXT) = 'ai_no_match_found' AND CAST(tem.selected_by AS TEXT) = 'ai')
      )
    ORDER BY COALESCE(lr.completed_at, lr.created_at, :epoch) ASC,
             tt.date DESC,
             tt.transaction_id ASC
    LIMIT :limit)sql"),
   Params{{"cutoff_date", Value(std::string(cutoff_date))}, {"epoch", Value(std::string("1970-01-01 00:00:00"))},
          {"limit", Value(static_cast<int64_t>(limit))}});
  std::vector<std::string> ids;
  for (const Row &row : rows) ids.push_back(RowText(row, "transaction_id"));
  return ids;
 }

 std::optional<nlohmann::json> MatchRepository::ReadLastRunSummary(Session &session,
                                                                   const std::string &transaction_id) const
 { std::optional<nlohmann::json> result;
  std::optional<Row> run_row = session.db().query_one(Sql(R"sql(
   SELECT match_run_id, CAST(status AS TEXT) AS status, model_name, prompt_version
     FROM matchy.transaction_email_match_run
    WHERE transaction_id = :transaction_id
    ORDER BY match_run_id DESC
    LIMIT 1)sql"), Params{{"transaction_id", Value(transaction_id)}});
  if (run_row.has_value())
  { long long match_run_id = run_row->get_int("match_run_id").value_or(0);
   std::vector<Row> candidate_rows = session.db().query(Sql(R"sql(
    SELECT email_message_id,
           email_received_at,
           score,
           reason_json,
           cached_subject,
           cached_sender,
           cached_snippet,
           is_unmatched_email_priority
      FROM matchy.transaction_email_candidate
     WHERE match_run_id = :match_run_id)sql"),
    Params{{"match_run_id", Value(static_cast<int64_t>(match_run_id))}});
   nlohmann::json cache_rows = nlohmann::json::array();
   for (const Row &row : candidate_rows)
   { std::optional<DbDatetime> received = AsDatetime(row.columns.at("email_received_at"));
    cache_rows.push_back({
     {"email_message_id", RowText(row, "email_message_id")},
     {"email_received_at", received.has_value() ? received->Iso() : ""},
     {"score", row.is_null("score") ? 0.0 : RowDouble(row, "score")},
     {"reason_json", ParsedReasonJson(row)},
     {"cached_subject", RowText(row, "cached_subject")},
     {"cached_sender", RowText(row, "cached_sender")},
     {"cached_snippet", RowText(row, "cached_snippet")},
     {"is_unmatched_email_priority", row.get_int("is_unmatched_email_priority").value_or(0) != 0}});
   }
   result = nlohmann::json{
    {"match_run_id", match_run_id},
    {"status", RowText(*run_row, "status")},
    {"model_name", RowText(*run_row, "model_name")},
    {"prompt_version", RowText(*run_row, "prompt_version")},
    {"candidate_cache_rows", cache_rows}};
  }
  return result;
 }

 std::optional<nlohmann::json> MatchRepository::ReadActiveMatchSummary(Session &session,
                                                                       const std::string &transaction_id) const
 { std::optional<nlohmann::json> result;
  std::optional<Row> row = session.db().query_one(Sql(R"sql(
   SELECT match_id, email_message_id, CAST(state AS TEXT) AS state,
          ai_confidence, CAST(selected_by AS TEXT) AS selected_by
     FROM matchy.transaction_email_match
    WHERE transaction_id = :transaction_id
      AND active = TRUE
    LIMIT 1)sql"), Params{{"transaction_id", Value(transaction_id)}});
  if (row.has_value())
  { nlohmann::json summary{
    {"match_id", row->get_int("match_id").value_or(0)},
    {"email_message_id", nullptr},
    {"state", RowText(*row, "state")},
    {"selected_by", RowText(*row, "selected_by")},
    {"ai_confidence", nullptr}};
   if (!row->is_null("email_message_id")) summary["email_message_id"] = RowText(*row, "email_message_id");
   if (!row->is_null("ai_confidence")) summary["ai_confidence"] = RowDouble(*row, "ai_confidence");
   result = summary;
  }
  return result;
 }

 std::set<std::string> MatchRepository::ListActiveEmailIdsForOtherTransactions(Session &session,
                                                                               const std::string &transaction_id) const
 { std::vector<Row> rows = session.db().query(Sql(R"sql(
   SELECT email_message_id
     FROM matchy.transaction_email_match
    WHERE active = TRUE
      AND email_message_id IS NOT NULL
      AND transaction_id <> :transaction_id)sql"), Params{{"transaction_id", Value(transaction_id)}});
  std::set<std::string> ids;
  for (const Row &row : rows) ids.insert(RowText(row, "email_message_id"));
  return ids;
 }

 void MatchRepository::UpdateRunStatus(Session &session, long long run_id, const std::string &status,
                                       const std::optional<std::string> &error_text) const
 { Params params{{"status", Value(status)}, {"match_run_id", Value(static_cast<int64_t>(run_id))}};
  params["error_text"] = error_text.has_value() ? Value(*error_text) : Value(std::monostate{});
  session.db().execute(Sql(R"sql(
   UPDATE matchy.transaction_email_match_run
      SET status = :status,
          completed_at = CURRENT_TIMESTAMP,
          error_text = :error_text
    WHERE match_run_id = :match_run_id)sql"), params);
 }

 void MatchRepository::MarkRunFailed(Session &session, long long run_id, const std::string &error_text) const
 { UpdateRunStatus(session, run_id, "failed", error_text);
 }
}
