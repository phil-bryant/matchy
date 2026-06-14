#pragma once
#include <filesystem>
#include <fstream>
#include <random>
#include <sstream>
#include <string>
#include "tellercore/db.hpp"
#include "tellercore/profile.hpp"
#include "matchycore/repository.hpp"
#include "matchycore/settings.hpp"

// SQLCipher-backed teller schema fixture mirroring tellercore's test fixture, with the minimal
// account graph one matchy transaction needs (institution -> account -> details -> transaction).
namespace matchycore::testfx
// #R001: Matchycore traceability test coverage.
{ inline std::string ReadFile(const std::string &path)
 { std::ifstream in(path);
  if (!in.is_open()) throw std::runtime_error("cannot open file: " + path);
  std::stringstream buffer;
  buffer << in.rdbuf();
  return buffer.str();
 }

 class Fixture
 { public:
// #R001: Matchycore traceability test coverage.
  Fixture()
  { std::random_device rd;
   dir_ = std::filesystem::temp_directory_path() / ("matchycore-test-" + std::to_string(rd()));
   std::filesystem::create_directories(dir_);
   db_path_ = (dir_ / "teller.sqlite3").string();
   tellercore::db::SqliteDb::bootstrap_file(db_path_, key_, ReadFile(TELLER_SQLITE_DDL_PATH));
   tellercore::db::SqliteDb seed(db_path_, key_);
   seed.execute_script(R"sql(
    INSERT INTO teller.institution (institution_id, name) VALUES ('inst-1', 'Test Bank');
    INSERT INTO teller.account_links (self_link) VALUES ('https://example/accounts/a1');
    INSERT INTO teller.account (currency, enrollment_id, account_id, institution_id, last_four,
                                account_links_id, name, type, subtype, status)
    VALUES ('USD', 'enr-1', 'acct-1', 'inst-1', '0001', 1, 'Checking', 'depository', 'checking', 'open');
    INSERT INTO teller.transaction_type (code) VALUES ('card_payment');
    INSERT INTO teller.transaction_details_counterparty (name, type) VALUES ('Blue Bottle Coffee', 'organization');
    INSERT INTO teller.transaction_details (processing_status, category, transaction_details_counterparty_id)
    VALUES ('complete', 'dining', 1);
    INSERT INTO teller.transaction_links (self_link, account) VALUES ('https://example/txn/t1', 'acct-1');
    INSERT INTO teller."transaction" (account_id, amount, date, description, transaction_details_id, status,
                                      transaction_id, transaction_links_id, transaction_type_id)
    VALUES ('acct-1', -1050, '2024-06-01', 'BLUE BOTTLE COFFEE purchase', 1, 'posted', 'txn-1', 1, 1);
    INSERT INTO teller.transaction_details (processing_status, category) VALUES ('complete', 'misc');
    INSERT INTO teller.transaction_links (self_link, account) VALUES ('https://example/txn/t2', 'acct-1');
    INSERT INTO teller."transaction" (account_id, amount, date, description, transaction_details_id, status,
                                      transaction_id, transaction_links_id, transaction_type_id)
    VALUES ('acct-1', -2030, '2024-06-02', 'CLOUD HOSTING LLC subscription', 2, 'posted', 'txn-2', 2, 1);
   )sql");
  }

// #R001: Matchycore traceability test coverage.
  ~Fixture()
  { std::error_code ec;
   std::filesystem::remove_all(dir_, ec);
  }

// #R001: Matchycore traceability test coverage.
  [[nodiscard]] tellercore::DbProfile Profile() const
  { tellercore::DbProfile profile;
   profile.name = "sqlite";
   profile.target = tellercore::DbTarget::kSqlite;
   profile.sqlite_path = db_path_;
   profile.sqlcipher_key = key_;
   return profile;
  }

// #R001: Matchycore traceability test coverage.
  [[nodiscard]] db::MatchRepository Repository(bool write_enabled = true) const
  { Settings settings;
   settings.set_write_enabled(write_enabled);
   return db::MatchRepository(settings, Profile());
  }

  private:
  std::filesystem::path dir_;
  std::string db_path_;
  std::string key_ = "matchycore-test-key";
 };
}
