// Unit coverage for the extracted matchy_api request-validation and error-mapping contract
// (FastAPI-parity rules: txn_ prefix on confirm, FastAPI-shaped 422 bodies, api.py status mapping).
#include <catch2/catch_test_macros.hpp>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/api_contract.hpp"

using matchycore::apicontract::ApiError;
using matchycore::apicontract::ErrorOutcome;
using nlohmann::json;
namespace apicontract = matchycore::apicontract;

TEST_CASE("ValidateConfirmBody enforces the teller txn_ prefix", "[api_contract]")
{ std::string transaction_id;
 std::string email_message_id;
 std::optional<std::string> note;
 json body = json{{"transaction_id", "0"}, {"email_message_id", "m-1"}};
 bool threw = false;
 try { apicontract::ValidateConfirmBody(body, transaction_id, email_message_id, note); }
 catch (const ApiError &error)
 { threw = true;
  REQUIRE(error.status() == 422);
  REQUIRE(error.has_body());
  REQUIRE(error.body()["detail"].is_array());
  REQUIRE(error.body()["detail"][0]["type"] == "string_pattern_mismatch");
  REQUIRE(error.body()["detail"][0]["loc"] == json::array({"body", "transaction_id"}));
 }
 REQUIRE(threw);
}

TEST_CASE("ValidateConfirmBody accepts a well-formed payload", "[api_contract]")
{ std::string transaction_id;
 std::string email_message_id;
 std::optional<std::string> note;
 json body = json{{"transaction_id", "txn_abc-123"}, {"email_message_id", "m-1"}, {"note", "ok"}};
 apicontract::ValidateConfirmBody(body, transaction_id, email_message_id, note);
 REQUIRE(transaction_id == "txn_abc-123");
 REQUIRE(email_message_id == "m-1");
 REQUIRE(note.has_value());
 REQUIRE(*note == "ok");
}

TEST_CASE("ValidateConfirmBody rejects an empty email_message_id", "[api_contract]")
{ std::string transaction_id;
 std::string email_message_id;
 std::optional<std::string> note;
 json body = json{{"transaction_id", "txn_abc"}, {"email_message_id", ""}};
 bool threw = false;
 try { apicontract::ValidateConfirmBody(body, transaction_id, email_message_id, note); }
 catch (const ApiError &error)
 { threw = true;
  REQUIRE(error.status() == 422);
  REQUIRE(error.body()["detail"][0]["loc"] == json::array({"body", "email_message_id"}));
 }
 REQUIRE(threw);
}

TEST_CASE("ValidateRunBody requires a non-empty bounded id list", "[api_contract]")
{ std::vector<std::string> transaction_ids;
 std::string trigger_source;
 bool force_rematch = false;
 json body = json{{"transaction_ids", json::array()}};
 bool threw = false;
 try { apicontract::ValidateRunBody(body, transaction_ids, trigger_source, force_rematch); }
 catch (const ApiError &error)
 { threw = true;
  REQUIRE(error.status() == 422);
  REQUIRE(error.body()["detail"][0]["type"] == "too_short");
 }
 REQUIRE(threw);
}

TEST_CASE("ValidateRunBody accepts valid ids and trigger source", "[api_contract]")
{ std::vector<std::string> transaction_ids;
 std::string trigger_source;
 bool force_rematch = false;
 json body = json{{"transaction_ids", json::array({"txn_1", "txn_2"})}, {"trigger_source", "retry"},
                  {"force_rematch", true}};
 apicontract::ValidateRunBody(body, transaction_ids, trigger_source, force_rematch);
 REQUIRE(transaction_ids.size() == 2);
 REQUIRE(trigger_source == "retry");
 REQUIRE(force_rematch);
}

TEST_CASE("ValidateRunBody rejects an unknown trigger source", "[api_contract]")
{ std::vector<std::string> transaction_ids;
 std::string trigger_source;
 bool force_rematch = false;
 json body = json{{"transaction_ids", json::array({"txn_1"})}, {"trigger_source", "bogus"}};
 bool threw = false;
 try { apicontract::ValidateRunBody(body, transaction_ids, trigger_source, force_rematch); }
 catch (const ApiError &error)
 { threw = true;
  REQUIRE(error.status() == 422);
  REQUIRE(error.body()["detail"][0]["type"] == "literal_error");
 }
 REQUIRE(threw);
}

TEST_CASE("ValidatePendingBody enforces limit and lookback bounds", "[api_contract]")
{ int limit = 0;
 int lookback_days = 0;
 std::string trigger_source;
 bool force_rematch = false;
 json body = json{{"limit", 9000}, {"lookback_days", 14}};
 bool threw = false;
 try { apicontract::ValidatePendingBody(body, limit, lookback_days, trigger_source, force_rematch); }
 catch (const ApiError &error)
 { threw = true;
  REQUIRE(error.status() == 422);
  REQUIRE(error.body()["detail"][0]["type"] == "less_than_equal");
 }
 REQUIRE(threw);
}

TEST_CASE("ValidatePendingBody applies api.py defaults", "[api_contract]")
{ int limit = 0;
 int lookback_days = 0;
 std::string trigger_source;
 bool force_rematch = false;
 apicontract::ValidatePendingBody(json::object(), limit, lookback_days, trigger_source, force_rematch);
 REQUIRE(limit == 100);
 REQUIRE(lookback_days == 14);
 REQUIRE(trigger_source == "auto");
}

TEST_CASE("MapError mirrors api.py status mapping", "[api_contract]")
{ ErrorOutcome structured = apicontract::MapError(ApiError::WithBody(422, json{{"detail", json::array()}}, "bad"));
 REQUIRE(structured.status() == 422);
 REQUIRE(structured.body()["detail"].is_array());

 ErrorOutcome unauthorized = apicontract::MapError(ApiError(401, "Unauthorized", true));
 REQUIRE(unauthorized.status() == 401);
 REQUIRE(unauthorized.unauthorized());

 ErrorOutcome not_found = apicontract::MapError(std::invalid_argument("Unknown transaction_id: txn_x"));
 REQUIRE(not_found.status() == 404);
 REQUIRE(not_found.body()["detail"] == "No transaction matched the supplied transaction_id.");

 ErrorOutcome internal = apicontract::MapError(std::runtime_error("boom"));
 REQUIRE(internal.status() == 500);
}
