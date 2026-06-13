#pragma once
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "matchycore/models.hpp"
#include "matchycore/settings.hpp"

// Port of matchy/ai_ranker.py (Anthropic -> OpenAI -> deterministic selection, prompt v3 preserved).
namespace matchycore::ai
{ inline constexpr const char *kPromptVersion = "v3";

 class AiError : public std::runtime_error
 { public:
  enum class Kind { kRateLimit, kStatus, kTransport };
  AiError(Kind kind, int status, const std::string &message, std::optional<double> retry_after = std::nullopt)
  : std::runtime_error(message), kind_(kind), status_(status), retry_after_(retry_after) {}
  [[nodiscard]] Kind kind() const { return kind_; }
  [[nodiscard]] int status() const { return status_; }
  [[nodiscard]] std::optional<double> retry_after_seconds() const { return retry_after_; }

  private:
  Kind kind_;
  int status_;
  std::optional<double> retry_after_;
 };

 // HTTP backend seam: production uses HTTPS to api.anthropic.com / api.openai.com; tests stub it.
 class AiTransport
 { public:
  virtual ~AiTransport() = default;
  virtual std::string CreateAnthropicMessage(const std::string &model, const std::string &user_text) = 0;
  virtual std::string CreateOpenAiResponse(const std::string &model, const std::string &user_text) = 0;
 };

 std::shared_ptr<AiTransport> MakeHttpTransport(const Settings &settings);

 class AiRanker
 { public:
  explicit AiRanker(const Settings &settings, std::shared_ptr<AiTransport> transport = nullptr);
  //R440: No-candidate, Anthropic, OpenAI, or deterministic selection in that priority order.
  AiSelection Select(const TransactionInput &transaction, const std::vector<RankedCandidate> &ranked_candidates);
  //R445: Model the ranker plans to use, for pre-run cache validity checks.
  [[nodiscard]] std::string PlannedModelName() const;
  //R455: Prompt payload from transaction context plus the top ranked candidate evidence.
  [[nodiscard]] nlohmann::ordered_json BuildPromptPayload(const TransactionInput &transaction,
                                                          const std::vector<RankedCandidate> &ranked_candidates,
                                                          int body_excerpt_cap = -1) const;
  //R460: Normalize body text to readable plain text and truncate to the cap.
  static std::string ExtractBodyExcerpt(const std::string &body_text, int max_chars = -1);
  //R465: Delimit untrusted body excerpts, redacting embedded delimiter tokens.
  static std::string DelimitUntrustedBodyExcerpt(const std::string &excerpt);
  //R475: Defensive JSON parse tolerating fenced/prose payloads with confidence clamping.
  [[nodiscard]] AiSelection ParseAiPayload(const std::string &text_payload, const std::string &backend) const;
  static std::string StripMarkdownFences(const std::string &text);
  static std::optional<std::string> ExtractFirstJsonObject(const std::string &text);

  private:
  AiSelection SelectDeterministic(const std::vector<RankedCandidate> &ranked_candidates) const;
  AiSelection SelectWithAnthropic(const TransactionInput &transaction,
                                  const std::vector<RankedCandidate> &ranked_candidates);
  AiSelection SelectWithOpenAi(const TransactionInput &transaction,
                               const std::vector<RankedCandidate> &ranked_candidates);
  Settings settings_;
  std::shared_ptr<AiTransport> transport_;
  bool anthropic_enabled_;
  bool openai_enabled_;
 };
}
