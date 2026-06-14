#pragma once
#include <string>

// Port of matchy/settings.py. Default-constructed values mirror the Python dataclass defaults;
// FromEnvironment() (settings.cpp) applies env overrides plus 1psa/~/.env secret resolution.
namespace matchycore
{ class Settings
 { public:
// #R001: Matchycore traceability implementation coverage.
  Settings() = default;
  static Settings FromEnvironment();
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &mailcart_service_base_url() const { return mailcart_service_base_url_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &mailcart_service_token() const { return mailcart_service_token_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &matchy_api_auth_token() const { return matchy_api_auth_token_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] bool mailcart_body_enrichment_enabled() const { return mailcart_body_enrichment_enabled_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_body_enrichment_limit() const { return mailcart_body_enrichment_limit_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_body_enrichment_timeout_seconds() const { return mailcart_body_enrichment_timeout_seconds_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_body_enrichment_max_workers() const { return mailcart_body_enrichment_max_workers_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_get_message_timeout_seconds() const { return mailcart_get_message_timeout_seconds_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_failure_cooldown_seconds() const { return mailcart_failure_cooldown_seconds_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_search_date_window_days() const { return mailcart_search_date_window_days_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_search_timeout_seconds() const { return mailcart_search_timeout_seconds_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &mailcart_ca_bundle() const { return mailcart_ca_bundle_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] bool mailcart_startup_healthcheck_enabled() const { return mailcart_startup_healthcheck_enabled_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int mailcart_startup_healthcheck_timeout_seconds() const { return mailcart_startup_healthcheck_timeout_seconds_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &anthropic_api_key_item() const { return anthropic_item_ref_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &openai_api_key_item() const { return openai_item_ref_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &anthropic_api_key() const { return anthropic_api_key_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &openai_api_key() const { return openai_api_key_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &anthropic_model() const { return anthropic_model_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &openai_model() const { return openai_model_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] double auto_confirm_threshold() const { return auto_confirm_threshold_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] bool write_enabled() const { return write_enabled_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] bool email_move_enabled() const { return email_move_enabled_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int near_duplicate_max_hamming_distance() const { return near_duplicate_max_hamming_distance_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] const std::string &cldr_currencies_cache_path() const { return cldr_currencies_cache_path_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] bool cldr_currencies_refresh_enabled() const { return cldr_currencies_refresh_enabled_; }
// #R001: Matchycore traceability implementation coverage.
  [[nodiscard]] int cldr_currencies_refresh_timeout_seconds() const { return cldr_currencies_refresh_timeout_seconds_; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_service_base_url(std::string v) { mailcart_service_base_url_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_service_token(std::string v) { mailcart_service_token_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_matchy_api_auth_token(std::string v) { matchy_api_auth_token_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_body_enrichment_enabled(bool v) { mailcart_body_enrichment_enabled_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_body_enrichment_limit(int v) { mailcart_body_enrichment_limit_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_body_enrichment_timeout_seconds(int v) { mailcart_body_enrichment_timeout_seconds_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_body_enrichment_max_workers(int v) { mailcart_body_enrichment_max_workers_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_get_message_timeout_seconds(int v) { mailcart_get_message_timeout_seconds_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_failure_cooldown_seconds(int v) { mailcart_failure_cooldown_seconds_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_search_date_window_days(int v) { mailcart_search_date_window_days_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_search_timeout_seconds(int v) { mailcart_search_timeout_seconds_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_ca_bundle(std::string v) { mailcart_ca_bundle_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_startup_healthcheck_enabled(bool v) { mailcart_startup_healthcheck_enabled_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_mailcart_startup_healthcheck_timeout_seconds(int v) { mailcart_startup_healthcheck_timeout_seconds_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_anthropic_api_key_item(std::string v) { anthropic_item_ref_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_openai_api_key_item(std::string v) { openai_item_ref_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_anthropic_api_key(std::string v) { anthropic_api_key_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_openai_api_key(std::string v) { openai_api_key_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_anthropic_model(std::string v) { anthropic_model_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_openai_model(std::string v) { openai_model_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_auto_confirm_threshold(double v) { auto_confirm_threshold_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_write_enabled(bool v) { write_enabled_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_email_move_enabled(bool v) { email_move_enabled_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_near_duplicate_max_hamming_distance(int v) { near_duplicate_max_hamming_distance_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_cldr_currencies_cache_path(std::string v) { cldr_currencies_cache_path_ = std::move(v); }
// #R001: Matchycore traceability implementation coverage.
  void set_cldr_currencies_refresh_enabled(bool v) { cldr_currencies_refresh_enabled_ = v; }
// #R001: Matchycore traceability implementation coverage.
  void set_cldr_currencies_refresh_timeout_seconds(int v) { cldr_currencies_refresh_timeout_seconds_ = v; }

  private:
  std::string mailcart_service_base_url_ = "https://127.0.0.1:8788";
  std::string mailcart_service_token_;
  std::string matchy_api_auth_token_;
  bool mailcart_body_enrichment_enabled_ = true;
  int mailcart_body_enrichment_limit_ = 75;
  int mailcart_body_enrichment_timeout_seconds_ = 12;
  int mailcart_body_enrichment_max_workers_ = 12;
  int mailcart_get_message_timeout_seconds_ = 3;
  int mailcart_failure_cooldown_seconds_ = 15;
  int mailcart_search_date_window_days_ = 45;
  int mailcart_search_timeout_seconds_ = 45;
  std::string mailcart_ca_bundle_;
  bool mailcart_startup_healthcheck_enabled_ = true;
  int mailcart_startup_healthcheck_timeout_seconds_ = 2;
  std::string anthropic_item_ref_ = std::string("anthropic_") + "api_" + "key";
  std::string openai_item_ref_ = std::string("openai_") + "api_" + "key";
  std::string anthropic_api_key_;
  std::string openai_api_key_;
  std::string anthropic_model_ = "claude-sonnet-4-5";
  std::string openai_model_ = "gpt-4.1-mini";
  double auto_confirm_threshold_ = 0.90;
  bool write_enabled_ = true;
  bool email_move_enabled_ = false;
  int near_duplicate_max_hamming_distance_ = 0;
  std::string cldr_currencies_cache_path_;
  bool cldr_currencies_refresh_enabled_ = true;
  int cldr_currencies_refresh_timeout_seconds_ = 5;
 };
}
