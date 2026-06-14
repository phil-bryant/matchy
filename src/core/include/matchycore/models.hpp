#pragma once
#include <chrono>
#include <string>
#include <utility>
#include <vector>
#include <nlohmann/json.hpp>

// Port of matchy/models.py: immutable value objects shared by scoring, search, and persistence.
namespace matchycore
{ using TimePoint = std::chrono::system_clock::time_point;

 class TransactionInput
 { public:
// #R001: Matchycore traceability implementation coverage.
  TransactionInput(std::string transaction_id, std::string account_id, std::string amount, TimePoint date,
                   std::string description, std::string counterparty_name = "")
  : transaction_id_(std::move(transaction_id)), account_id_(std::move(account_id)), amount_(std::move(amount)),
    date_(date), description_(std::move(description)), counterparty_name_(std::move(counterparty_name)) {}
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &transaction_id() const { return transaction_id_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &account_id() const { return account_id_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &amount() const { return amount_; } // decimal string, e.g. "-42.50"
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] TimePoint date() const { return date_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &description() const { return description_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &counterparty_name() const { return counterparty_name_; }

  private:
  std::string transaction_id_;
  std::string account_id_;
  std::string amount_;
  TimePoint date_;
  std::string description_;
  std::string counterparty_name_;
 };

 class EmailCandidate
 { public:
// #R001: Matchycore traceability implementation coverage.
  EmailCandidate(std::string message_id, std::string subject, std::string preview, TimePoint received_at,
                 std::string sender = "", std::string body_text = "")
  : message_id_(std::move(message_id)), subject_(std::move(subject)), preview_(std::move(preview)),
    received_at_(received_at), sender_(std::move(sender)), body_text_(std::move(body_text)) {}
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &message_id() const { return message_id_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &subject() const { return subject_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &preview() const { return preview_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] TimePoint received_at() const { return received_at_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &sender() const { return sender_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &body_text() const { return body_text_; }

  private:
  std::string message_id_;
  std::string subject_;
  std::string preview_;
  TimePoint received_at_;
  std::string sender_;
  std::string body_text_;
 };

 class RankedCandidate
 { public:
// #R001: Matchycore traceability implementation coverage.
  RankedCandidate(EmailCandidate candidate, double score, nlohmann::json reasons = nlohmann::json::object())
  : candidate_(std::move(candidate)), score_(score), reasons_(std::move(reasons)) {}
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const EmailCandidate &candidate() const { return candidate_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] double score() const { return score_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const nlohmann::json &reasons() const { return reasons_; }

  private:
  EmailCandidate candidate_;
  double score_;
  nlohmann::json reasons_;
 };

 class AiSelection
 { public:
// #R001: Matchycore traceability implementation coverage.
  AiSelection(std::vector<std::string> selected_message_ids, double confidence, bool uncertain,
              std::string rationale, std::string backend = "deterministic", std::string model_name = "deterministic")
  : selected_message_ids_(std::move(selected_message_ids)), confidence_(confidence), uncertain_(uncertain),
    rationale_(std::move(rationale)), backend_(std::move(backend)), model_name_(std::move(model_name)) {}
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::vector<std::string> &selected_message_ids() const { return selected_message_ids_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] double confidence() const { return confidence_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] bool uncertain() const { return uncertain_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &rationale() const { return rationale_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &backend() const { return backend_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &model_name() const { return model_name_; }

  private:
  std::vector<std::string> selected_message_ids_;
  double confidence_;
  bool uncertain_;
  std::string rationale_;
  std::string backend_;
  std::string model_name_;
 };
}
