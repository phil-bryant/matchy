cmake_minimum_required(VERSION 3.24)
project(matchycore LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Match the eggnest desktop platform floor used by classycore/tellercore so all
# native artifacts across sibling repos stay linkable from the same toolchains.
if(APPLE AND NOT CMAKE_OSX_DEPLOYMENT_TARGET)
  set(CMAKE_OSX_DEPLOYMENT_TARGET "14.0" CACHE STRING "" FORCE)
endif()

option(MATCHYCORE_BUILD_TESTS "Build matchycore unit tests" ON)
option(MATCHYCORE_BUILD_TOOLS "Build the API server, driver CLI, and oracle runner" ON)
option(MATCHYCORE_SANITIZE "Build with ASan+UBSan" OFF)
# OFF would drop Mailcart/AI/HTTP server support (e.g. for scoring-only embeddings).
option(MATCHYCORE_ENABLE_HTTP "Build Mailcart client, AI ranker, API server, and driver" ON)
# OFF skips the Teller DB layer (repository/match_writer/caching) and the tellercore link.
option(MATCHYCORE_ENABLE_DB "Build the Teller DB layer on top of libtellercore" ON)
set(MATCHYCORE_TELLER_CORE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../teller/src/core"
  CACHE PATH "Path to the sibling teller repo's C++ core")

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE RelWithDebInfo)
endif()

add_compile_options(-Wall -Wextra -Wpedantic -Werror)
if(MATCHYCORE_SANITIZE)
  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()

find_package(Threads REQUIRED)

include(FetchContent)
FetchContent_Declare(nlohmann_json
  URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
  DOWNLOAD_EXTRACT_TIMESTAMP ON)
FetchContent_MakeAvailable(nlohmann_json)

if(MATCHYCORE_ENABLE_HTTP)
  find_package(OpenSSL REQUIRED)
  set(HTTPLIB_USE_BROTLI_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
  set(HTTPLIB_USE_ZSTD_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(httplib
    URL https://github.com/yhirose/cpp-httplib/archive/refs/tags/v0.18.3.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP ON)
  FetchContent_MakeAvailable(httplib)
endif()

if(MATCHYCORE_ENABLE_DB)
  # Reuse the sibling teller repo's C++ core for profile resolution, SQLCipher and
  # Postgres backends, and 1psa secrets instead of forking a private DB layer.
  set(TELLERCORE_BUILD_TESTS OFF CACHE BOOL "" FORCE)
  set(TELLERCORE_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
  add_subdirectory("${MATCHYCORE_TELLER_CORE_DIR}" tellercore EXCLUDE_FROM_ALL)
endif()

set(MATCHYCORE_SOURCES
  src/version.cpp
  src/timeutil.cpp
  src/scoring.cpp
  src/near_duplicate.cpp)
if(MATCHYCORE_ENABLE_HTTP)
  list(APPEND MATCHYCORE_SOURCES src/mailcart.cpp src/search.cpp src/enrichment.cpp src/cldr.cpp src/ai_ranker.cpp)
endif()
if(MATCHYCORE_ENABLE_DB)
  list(APPEND MATCHYCORE_SOURCES src/settings.cpp src/repository.cpp src/match_writer.cpp src/caching.cpp)
  # teller's core no longer links libonepsa (it is a Python-side concern for teller's DB layer),
  # but matchy still resolves optional AI-key 1psa items in C++. Reuse teller's onepsa.cpp
  # implementation directly instead of forking the secret reader.
  list(APPEND MATCHYCORE_SOURCES "${MATCHYCORE_TELLER_CORE_DIR}/src/onepsa.cpp")
endif()
if(MATCHYCORE_ENABLE_HTTP AND MATCHYCORE_ENABLE_DB)
  list(APPEND MATCHYCORE_SOURCES src/match_service.cpp)
endif()

add_library(matchycore STATIC ${MATCHYCORE_SOURCES})
target_include_directories(matchycore PUBLIC include)
target_link_libraries(matchycore
  PUBLIC nlohmann_json::nlohmann_json
  PRIVATE Threads::Threads)
if(MATCHYCORE_ENABLE_HTTP)
  target_compile_definitions(matchycore PUBLIC MATCHYCORE_ENABLE_HTTP=1)
  target_link_libraries(matchycore PRIVATE httplib::httplib OpenSSL::SSL OpenSSL::Crypto)
endif()
if(MATCHYCORE_ENABLE_DB)
  target_compile_definitions(matchycore PUBLIC MATCHYCORE_ENABLE_DB=1)
  target_link_libraries(matchycore PUBLIC tellercore)
endif()

if(MATCHYCORE_BUILD_TOOLS AND MATCHYCORE_ENABLE_HTTP AND MATCHYCORE_ENABLE_DB)
  add_executable(matchy_api tools/matchy_api.cpp)
  target_link_libraries(matchy_api PRIVATE matchycore httplib::httplib OpenSSL::SSL OpenSSL::Crypto)

  add_executable(matchy_driver tools/matchy_driver.cpp)
  target_link_libraries(matchy_driver PRIVATE matchycore httplib::httplib OpenSSL::SSL OpenSSL::Crypto)

  add_executable(matchy_oracle_runner tools/oracle_runner.cpp)
  target_link_libraries(matchy_oracle_runner PRIVATE matchycore)
endif()

if(MATCHYCORE_BUILD_TESTS)
  FetchContent_Declare(catch2
    URL https://github.com/catchorg/Catch2/archive/refs/tags/v3.7.1.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP ON)
  FetchContent_MakeAvailable(catch2)
  enable_testing()
  set(MATCHYCORE_TEST_SOURCES
    tests/test_smoke.cpp
    tests/test_scoring.cpp
    tests/test_near_duplicate.cpp)
  if(MATCHYCORE_ENABLE_HTTP)
    list(APPEND MATCHYCORE_TEST_SOURCES
      tests/test_mailcart.cpp tests/test_search.cpp tests/test_enrichment.cpp tests/test_cldr.cpp tests/test_ai_ranker.cpp)
  endif()
  if(MATCHYCORE_ENABLE_DB)
    list(APPEND MATCHYCORE_TEST_SOURCES tests/test_settings.cpp tests/test_repository.cpp)
  endif()
  if(MATCHYCORE_ENABLE_HTTP AND MATCHYCORE_ENABLE_DB)
    list(APPEND MATCHYCORE_TEST_SOURCES tests/test_service.cpp)
  endif()
  add_executable(matchycore_tests ${MATCHYCORE_TEST_SOURCES})
  target_link_libraries(matchycore_tests PRIVATE matchycore Catch2::Catch2WithMain)
  if(MATCHYCORE_ENABLE_DB)
    get_filename_component(MATCHY_TELLER_SQLITE_DDL
      "${MATCHYCORE_TELLER_CORE_DIR}/../sql/sqlite/create_database.sql" ABSOLUTE)
    target_compile_definitions(matchycore_tests PRIVATE
      TELLER_SQLITE_DDL_PATH="${MATCHY_TELLER_SQLITE_DDL}")
  endif()
  if(MATCHYCORE_ENABLE_HTTP)
    target_link_libraries(matchycore_tests PRIVATE httplib::httplib OpenSSL::SSL OpenSSL::Crypto)
  endif()
  add_test(NAME matchycore_tests COMMAND matchycore_tests)
endif()
