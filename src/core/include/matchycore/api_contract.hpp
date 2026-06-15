// Pure request-validation and error-mapping contract shared by the C++ matchy_api server and its
// Catch2 tests. Extracted from tools/matchy_api.cpp so the FastAPI-parity rules (txn_ prefix on
// confirm, FastAPI-shaped 422 bodies, api.py status mapping) are unit-testable in isolation.
#pragma once
#include <optional>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>

namespace matchycore::apicontract
{ using nlohmann::json;

 // #R001: HTTP-shaped failure carried out of handlers to one central response mapper.
 class ApiError : public std::runtime_error
 { public:
  // #R001: String-detail variant for plain {"detail": "..."} responses.
  ApiError(int status, std::string detail, bool unauthorized = false)
  : std::runtime_error(detail), status_(status), detail_(std::move(detail)), unauthorized_(unauthorized) {}
  // #R001: Build a structured-body error carrying a FastAPI-shaped validation payload.
  static ApiError WithBody(int status, json body, std::string message)
  { ApiError error(status, std::move(message), false);
   error.body_ = std::move(body);
   return error;
  }
  // #R001: HTTP status code mapped onto the response.
  [[nodiscard]] int status() const { return status_; }
  // #R001: Plain detail text used when no structured body is present.
  [[nodiscard]] const std::string &detail() const { return detail_; }
  // #R001: Whether to emit the WWW-Authenticate: Bearer challenge header.
  [[nodiscard]] bool unauthorized() const { return unauthorized_; }
  // #R001: Whether a structured FastAPI-shaped body is attached.
  [[nodiscard]] bool has_body() const { return body_.has_value(); }
  // #R001: The attached structured body (only valid when has_body()).
  [[nodiscard]] const json &body() const { return *body_; }

  private:
  int status_;
  std::string detail_;
  bool unauthorized_;
  std::optional<json> body_;
 };

 // #R001: Value carrier describing the response to emit for a caught exception.
 class ErrorOutcome
 { public:
  // #R001: Bind the status, body, and auth-challenge flag for one error response.
  ErrorOutcome(int status, json body, bool unauthorized)
  : status_(status), body_(std::move(body)), unauthorized_(unauthorized) {}
  // #R001: HTTP status code to write.
  [[nodiscard]] int status() const { return status_; }
  // #R001: JSON body to write.
  [[nodiscard]] const json &body() const { return body_; }
  // #R001: Whether to emit the WWW-Authenticate: Bearer challenge header.
  [[nodiscard]] bool unauthorized() const { return unauthorized_; }

  private:
  int status_;
  json body_;
  bool unauthorized_;
 };

 // #R001: Build one FastAPI-style validation error entry (type/loc/msg/input).
 inline json ValidationEntry(json loc, const std::string &msg, const std::string &type, json input)
 { return json{{"type", type}, {"loc", std::move(loc)}, {"msg", msg}, {"input", std::move(input)}};
 }

 // #R001: Wrap a list of validation entries into the FastAPI {"detail":[...]} body.
 inline json ValidationBody(json entries)
 { return json{{"detail", std::move(entries)}};
 }

 // #R001: R005: Validate the explicit-id run body (1..200 non-empty ids, enumerated trigger source).
 inline void ValidateRunBody(const json &body, std::vector<std::string> &transaction_ids,
                             std::string &trigger_source, bool &force_rematch)
 { json errors = json::array();
  bool has_ids = body.is_object() && body.contains("transaction_ids") && body["transaction_ids"].is_array();
  if (!has_ids)
   errors.push_back(ValidationEntry(json::array({"body", "transaction_ids"}), "Field required", "missing", body));
  if (has_ids && body["transaction_ids"].empty())
   errors.push_back(ValidationEntry(json::array({"body", "transaction_ids"}),
    "List should have at least 1 item after validation, not 0", "too_short", json::array()));
  if (has_ids && body["transaction_ids"].size() > 200)
   errors.push_back(ValidationEntry(json::array({"body", "transaction_ids"}),
    "List should have at most 200 items after validation, not " + std::to_string(body["transaction_ids"].size()),
    "too_long", json(nullptr)));
  if (has_ids)
  { int index = 0;
   for (const json &item : body["transaction_ids"])
   { if (!item.is_string() || item.get<std::string>().empty())
     errors.push_back(ValidationEntry(json::array({"body", "transaction_ids", index}),
      "String should have at least 1 character", "string_too_short", item));
    index += 1;
   }
  }
  trigger_source = body.is_object() ? body.value("trigger_source", std::string("manual")) : std::string("manual");
  if (trigger_source != "auto" && trigger_source != "manual" && trigger_source != "retry")
   errors.push_back(ValidationEntry(json::array({"body", "trigger_source"}),
    "Input should be 'auto', 'manual' or 'retry'", "literal_error", trigger_source));
  force_rematch = body.is_object() ? body.value("force_rematch", false) : false;
  if (!errors.empty()) throw ApiError::WithBody(422, ValidationBody(errors), "Invalid run request body.");
  for (const json &item : body["transaction_ids"]) transaction_ids.push_back(item.get<std::string>());
 }

 // #R001: Validate the pending-run body (bounded limit/lookback, enumerated trigger source).
 inline void ValidatePendingBody(const json &body, int &limit, int &lookback_days, std::string &trigger_source,
                                 bool &force_rematch)
 { json errors = json::array();
  limit = body.is_object() ? body.value("limit", 100) : 100;
  lookback_days = body.is_object() ? body.value("lookback_days", 14) : 14;
  trigger_source = body.is_object() ? body.value("trigger_source", std::string("auto")) : std::string("auto");
  force_rematch = body.is_object() ? body.value("force_rematch", false) : false;
  if (limit < 1)
   errors.push_back(ValidationEntry(json::array({"body", "limit"}),
    "Input should be greater than or equal to 1", "greater_than_equal", limit));
  if (limit > 500)
   errors.push_back(ValidationEntry(json::array({"body", "limit"}),
    "Input should be less than or equal to 500", "less_than_equal", limit));
  if (lookback_days < 1)
   errors.push_back(ValidationEntry(json::array({"body", "lookback_days"}),
    "Input should be greater than or equal to 1", "greater_than_equal", lookback_days));
  if (lookback_days > 365)
   errors.push_back(ValidationEntry(json::array({"body", "lookback_days"}),
    "Input should be less than or equal to 365", "less_than_equal", lookback_days));
  if (trigger_source != "auto" && trigger_source != "manual" && trigger_source != "retry")
   errors.push_back(ValidationEntry(json::array({"body", "trigger_source"}),
    "Input should be 'auto', 'manual' or 'retry'", "literal_error", trigger_source));
  if (!errors.empty()) throw ApiError::WithBody(422, ValidationBody(errors), "Invalid pending run request body.");
 }

 // #R001: Validate confirm body; enforce teller txn_ prefix and reject the null byte Postgres jsonb rejects.
 inline void ValidateConfirmBody(const json &body, std::string &transaction_id, std::string &email_message_id,
                                 std::optional<std::string> &note)
 { json errors = json::array();
  static const std::regex kTxnPattern("^txn_[A-Za-z0-9_-]+$");
  transaction_id = body.is_object() ? body.value("transaction_id", std::string()) : std::string();
  email_message_id = body.is_object() ? body.value("email_message_id", std::string()) : std::string();
  note = std::nullopt;
  if (transaction_id.empty())
   errors.push_back(ValidationEntry(json::array({"body", "transaction_id"}),
    "String should have at least 1 character", "string_too_short", transaction_id));
  else if (!std::regex_match(transaction_id, kTxnPattern))
   errors.push_back(ValidationEntry(json::array({"body", "transaction_id"}),
    "String should match pattern '^txn_[A-Za-z0-9_-]+$'", "string_pattern_mismatch", transaction_id));
  if (email_message_id.empty())
   errors.push_back(ValidationEntry(json::array({"body", "email_message_id"}),
    "String should have at least 1 character", "string_too_short", email_message_id));
  if (body.is_object() && body.contains("note") && !body["note"].is_null())
  { std::string note_value = body["note"].get<std::string>();
   if (note_value.find('\0') != std::string::npos)
    errors.push_back(ValidationEntry(json::array({"body", "note"}),
     "String should match pattern '^[^\\x00]*$'", "string_pattern_mismatch", note_value));
   note = note_value;
  }
  if (!errors.empty()) throw ApiError::WithBody(422, ValidationBody(errors), "Invalid confirm request body.");
 }

 // #R001: Translate a caught exception into the response outcome, matching api.py status mapping.
 inline ErrorOutcome MapError(const std::exception &error)
 { int status = 500;
  json body = json{{"detail", "Internal server error."}};
  bool unauthorized = false;
  if (const ApiError *api_error = dynamic_cast<const ApiError *>(&error))
  { status = api_error->status();
   body = api_error->has_body() ? api_error->body() : json{{"detail", api_error->detail()}};
   unauthorized = api_error->unauthorized();
  }
  else if (dynamic_cast<const std::invalid_argument *>(&error) != nullptr)
  { status = 404;
   body = json{{"detail", "No transaction matched the supplied transaction_id."}};
  }
  return ErrorOutcome(status, std::move(body), unauthorized);
 }
}
