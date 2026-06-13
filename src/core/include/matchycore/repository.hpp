#pragma once
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "tellercore/db.hpp"
#include "tellercore/profile.hpp"
#include "matchycore/models.hpp"
#include "matchycore/settings.hpp"

// Port of matchy/repository.py, matchy/match_writer.py, and matchy/db_target.py over tellercore::db.
namespace matchycore::db
{ //R035: Render owned-schema SQL (matchy.<t>/classy.<t>, teller.transaction) for the active backend.
 std::string SqlForTarget(const std::string &sql_text, bool is_sqlite);

 //R040: jsonb parameters are Postgres-typed; SQLite stores JSON as plain text.
 std::string JsonbParam(const std::string &param_name, bool is_sqlite);

 //R040: Bind timestamps as "Y-m-d H:M:S" text on SQLite (CURRENT_TIMESTAMP parity), ISO text on Postgres.
 tellercore::db::Value BindTimestamp(TimePoint value, bool is_sqlite);

 class DbDatetime
 { public:
  DbDatetime(TimePoint value, bool had_offset) : value_(value), had_offset_(had_offset) {}
  [[nodiscard]] TimePoint value() const { return value_; }
  // Python's isoformat() keeps the offset only when the source was tz-aware (postgres timestamptz).
  [[nodiscard]] std::string Iso() const;

  private:
  TimePoint value_;
  bool had_offset_;
 };

 //R040: Normalize date/timestamp column values read from either backend.
 std::optional<DbDatetime> AsDatetime(const tellercore::db::Value &value);

 //R005: Unit-of-work session: commit when write-enabled, rollback otherwise or on abandonment.
 class Session
 { public:
  Session(std::unique_ptr<tellercore::db::Db> db, bool write_enabled);
  ~Session();
  Session(const Session &) = delete;
  Session &operator=(const Session &) = delete;
  [[nodiscard]] tellercore::db::Db &db() { return *db_; }
  void Complete();
  void Abort();

  private:
  std::unique_ptr<tellercore::db::Db> db_;
  bool write_enabled_;
  bool finished_ = false;
 };

 class MatchRepository
 { public:
  //R001: Bind to the profile-driven teller DB engine (Postgres or SQLite/SQLCipher) via tellercore.
  explicit MatchRepository(const Settings &settings);
  MatchRepository(const Settings &settings, tellercore::DbProfile profile);
  [[nodiscard]] bool is_sqlite() const { return is_sqlite_; }
  [[nodiscard]] std::unique_ptr<Session> OpenSession() const;
  //R720: Load one transaction (with optional counterparty) normalized into TransactionInput (UTC date).
  std::optional<TransactionInput> LoadTransaction(Session &session, const std::string &transaction_id) const;
  //R721: Create a needs_review match run row and return its generated id.
  long long CreateRun(Session &session, const std::string &transaction_id, const std::string &trigger_source,
                      const std::string &model_name, const std::string &prompt_version) const;
  //R722: Update an existing run's recorded model name.
  void UpdateRunModelName(Session &session, long long run_id, const std::string &model_name) const;
  //R010: Deterministic pending transaction ids whose active match is not settled.
  std::vector<std::string> ListPendingTransactionIds(Session &session, int limit, int lookback_days) const;
  //R015: Most recent run summary plus the stored candidate payload that run scored.
  std::optional<nlohmann::json> ReadLastRunSummary(Session &session, const std::string &transaction_id) const;
  //R015: Active match row summary for cache-hit echoes.
  std::optional<nlohmann::json> ReadActiveMatchSummary(Session &session, const std::string &transaction_id) const;
  //R723: Active email ids already attached to other transactions.
  std::set<std::string> ListActiveEmailIdsForOtherTransactions(Session &session, const std::string &transaction_id) const;
  //R724 R725: Run status transitions.
  void UpdateRunStatus(Session &session, long long run_id, const std::string &status,
                       const std::optional<std::string> &error_text) const;
  void MarkRunFailed(Session &session, long long run_id, const std::string &error_text) const;
  //R680: Persist ranked candidates with cached_* columns at insert time.
  void InsertCandidates(Session &session, long long match_run_id, const std::string &transaction_id,
                        const std::vector<RankedCandidate> &candidates,
                        const std::set<std::string> &ai_selected_ids) const;
  //R685: Whether a candidate email already has an active match row.
  bool HasActiveMatch(Session &session, const std::string &email_message_id) const;
  //R690: Persist AI selection outcomes into match rows + run status; returns selected message ids.
  std::vector<std::string> PersistAiResult(Session &session, const std::string &transaction_id, long long run_id,
                                           const std::vector<RankedCandidate> &ranked_candidates,
                                           const AiSelection &ai_selection, double auto_confirm_threshold) const;
  //R695: Deactivate all active match rows for a transaction.
  void DeactivateActiveMatch(Session &session, const std::string &transaction_id) const;
  //R700: Insert and return a human-confirmed match row id.
  long long InsertHumanConfirmedMatch(Session &session, const std::string &transaction_id,
                                      const std::string &email_message_id,
                                      const std::optional<std::string> &note) const;

  private:
  [[nodiscard]] std::string Sql(const std::string &sql_text) const { return SqlForTarget(sql_text, is_sqlite_); }
  long long LastInsertId(Session &session, const std::string &id_column, const std::string &insert_sql,
                         const tellercore::db::Params &params) const;
  tellercore::DbProfile profile_;
  bool write_enabled_;
  bool is_sqlite_;
 };
}
