// Port of the transport-free contracts from tests/py/test_mailcart_client.py.
#include <catch2/catch_test_macros.hpp>
#include <chrono>
#include "matchycore/mailcart.hpp"
#include "matchycore/timeutil.hpp"

using matchycore::Settings;
using matchycore::mailcart::MailcartClient;
namespace timeutil = matchycore::timeutil;

TEST_CASE("base url must be https with a host", "[mailcart]")
{ REQUIRE_THROWS_AS(MailcartClient::ValidateBaseUrl("http://127.0.0.1:8788"), std::runtime_error);
 REQUIRE_THROWS_AS(MailcartClient::ValidateBaseUrl("ftp://127.0.0.1"), std::runtime_error);
 REQUIRE_THROWS_AS(MailcartClient::ValidateBaseUrl("https://"), std::runtime_error);
 REQUIRE_NOTHROW(MailcartClient::ValidateBaseUrl("https://127.0.0.1:8788"));
}

TEST_CASE("client construction rejects non-https settings", "[mailcart]")
{ Settings settings;
 settings.set_mailcart_service_base_url("http://127.0.0.1:8788");
 REQUIRE_THROWS_AS(MailcartClient(settings), std::runtime_error);
}

TEST_CASE("explicit ca bundle override must exist", "[mailcart]")
{ Settings settings;
 settings.set_mailcart_ca_bundle("/nonexistent/path/rootCA.pem");
 REQUIRE_THROWS_AS(MailcartClient::ResolveCaBundle(settings), std::runtime_error);
}

TEST_CASE("parse_datetime handles blank zulu and naive values", "[mailcart]")
{ matchycore::TimePoint before = std::chrono::system_clock::now() - std::chrono::seconds(5);
 matchycore::TimePoint after = std::chrono::system_clock::now() + std::chrono::seconds(5);
 matchycore::TimePoint blank = MailcartClient::ParseDatetime("");
 REQUIRE(blank > before);
 REQUIRE(blank < after);
 matchycore::TimePoint zulu = MailcartClient::ParseDatetime("2024-06-01T12:00:00Z");
 REQUIRE(timeutil::FormatIsoUtc(zulu) == "2024-06-01T12:00:00+00:00");
 matchycore::TimePoint naive = MailcartClient::ParseDatetime("2024-06-01T12:00:00");
 REQUIRE(naive == zulu);
 matchycore::TimePoint offset = MailcartClient::ParseDatetime("2024-06-01T14:00:00+02:00");
 REQUIRE(offset == zulu);
 REQUIRE_THROWS_AS(MailcartClient::ParseDatetime("not-a-date"), std::runtime_error);
}

TEST_CASE("iso formatting matches python isoformat", "[mailcart]")
{ matchycore::TimePoint with_micros = *timeutil::ParseIso8601("2024-06-01T12:00:00.123456+00:00");
 REQUIRE(timeutil::FormatIsoUtc(with_micros) == "2024-06-01T12:00:00.123456+00:00");
 REQUIRE(timeutil::UtcDateString(with_micros, 0) == "2024-06-01");
 REQUIRE(timeutil::UtcDateString(with_micros, -45) == "2024-04-17");
 REQUIRE(timeutil::UtcDateString(with_micros, 45) == "2024-07-16");
}
