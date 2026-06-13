#include <catch2/catch_test_macros.hpp>
#include "matchycore/version.hpp"

TEST_CASE("version is populated", "[smoke]")
{ REQUIRE_FALSE(matchycore::Version().empty());
}
