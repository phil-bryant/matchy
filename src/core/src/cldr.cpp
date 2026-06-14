#include "matchycore/cldr.hpp"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sys/stat.h>
#include <httplib.h>

namespace matchycore::cldr
{ namespace
// #R001: Matchycore traceability implementation coverage.
 { bool IsAsciiAlpha(char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }

// #R001: Matchycore traceability implementation coverage.
  bool IsAsciiAlnum(char c) { return IsAsciiAlpha(c) || (c >= '0' && c <= '9'); }

// #R001: Matchycore traceability implementation coverage.
  std::vector<char32_t> Utf8Codepoints(const std::string &value)
  { std::vector<char32_t> points;
   std::size_t i = 0;
   while (i < value.size())
   { unsigned char byte = static_cast<unsigned char>(value[i]);
    char32_t cp = byte;
    std::size_t extra = 0;
    if ((byte & 0xe0) == 0xc0) { cp = byte & 0x1f; extra = 1; }
    else if ((byte & 0xf0) == 0xe0) { cp = byte & 0x0f; extra = 2; }
    else if ((byte & 0xf8) == 0xf0) { cp = byte & 0x07; extra = 3; }
    std::size_t consumed = 1;
    while (consumed <= extra && i + consumed < value.size())
    { cp = (cp << 6) | (static_cast<unsigned char>(value[i + consumed]) & 0x3f);
     consumed += 1;
    }
    points.push_back(cp);
    i += consumed;
   }
   return points;
  }

  // Unicode Sc (currency symbol) category codepoints (Unicode 15 ranges).
// #R001: Matchycore traceability implementation coverage.
  bool IsCurrencyCategory(char32_t cp)
  { return cp == 0x24 || (cp >= 0xa2 && cp <= 0xa5) || cp == 0x58f || cp == 0x60b || (cp >= 0x7fe && cp <= 0x7ff)
    || (cp >= 0x9f2 && cp <= 0x9f3) || cp == 0x9fb || cp == 0xaf1 || cp == 0xbf9 || cp == 0xe3f || cp == 0x17db
    || (cp >= 0x20a0 && cp <= 0x20c0) || cp == 0xa838 || cp == 0xfdfc || cp == 0xfe69 || cp == 0xff04
    || (cp >= 0xffe0 && cp <= 0xffe1) || (cp >= 0xffe5 && cp <= 0xffe6) || (cp >= 0x11fdd && cp <= 0x11fe0)
    || cp == 0x1e2ff || cp == 0x1ecb0;
  }

// #R001: Matchycore traceability implementation coverage.
  std::string Strip(const std::string &value)
  { std::size_t begin = value.find_first_not_of(" \t\n\r\f\v");
   std::string out;
   if (begin != std::string::npos) out = value.substr(begin, value.find_last_not_of(" \t\n\r\f\v") - begin + 1);
   return out;
  }

// #R001: Matchycore traceability implementation coverage.
  bool IsThreeLetterAlpha(const std::string &token)
  { bool ok = token.size() == 3;
   for (char c : token)
    if (!IsAsciiAlpha(c)) ok = false;
   return ok;
  }

// #R001: Matchycore traceability implementation coverage.
  std::string Upper(const std::string &value)
  { std::string out = value;
   for (char &c : out)
    if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
   return out;
  }

  // #R001: Classify placeholder symbols (currency placeholder, arrows, non-currency punctuation).
  bool IsPlaceholderSymbol(const std::string &symbol)
  { bool placeholder = symbol.empty() || symbol == "\u00a4" || symbol.rfind("\u2191", 0) == 0;
   if (!placeholder)
   { std::vector<char32_t> points = Utf8Codepoints(symbol);
    if (points.size() == 1)
    { bool alnum = points[0] < 128 && IsAsciiAlnum(static_cast<char>(points[0]));
     placeholder = !IsCurrencyCategory(points[0]) && !alnum;
    }
   }
   return placeholder;
  }

// #R001: Matchycore traceability implementation coverage.
  std::string CleanSymbol(const nlohmann::json &value)
  { std::string symbol = value.is_string() ? Strip(value.get<std::string>()) : "";
   if (IsPlaceholderSymbol(symbol)) symbol = "";
   return symbol;
  }

  // #R001: Require non-letter boundaries around symbol tokens to reject embedded substring matches.
  bool SymbolStandaloneAt(const std::string &symbol, const std::string &text, std::size_t position)
  { bool symbol_alnum = !symbol.empty();
   for (char c : symbol)
    if (!IsAsciiAlnum(c)) symbol_alnum = false;
   char left = position > 0 ? text[position - 1] : '\0';
   std::size_t right_index = position + symbol.size();
   char right = right_index < text.size() ? text[right_index] : '\0';
   bool left_ok = symbol_alnum ? !IsAsciiAlnum(left) : !IsAsciiAlpha(left);
   bool right_ok = symbol_alnum ? !IsAsciiAlnum(right) : !IsAsciiAlpha(right);
   return left_ok && right_ok;
  }

// #R001: Matchycore traceability implementation coverage.
  bool SymbolOccursStandalone(const std::string &symbol, const std::string &text)
  { bool found = false;
   std::size_t start = 0;
   bool scanning = !symbol.empty();
   while (!found && scanning)
   { std::size_t position = text.find(symbol, start);
    if (position == std::string::npos) scanning = false;
    else
    { found = SymbolStandaloneAt(symbol, text, position);
     start = position + 1;
    }
   }
   return found;
  }

// #R001: Matchycore traceability implementation coverage.
  bool CodeOccursStandalone(const std::string &code_upper, const std::string &text)
  { bool found = false;
   for (std::size_t i = 0; !found && i + code_upper.size() <= text.size(); i += 1)
   { bool matches = true;
    for (std::size_t k = 0; matches && k < code_upper.size(); k += 1)
    { char c = text[i + k];
     if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
     matches = c == code_upper[k];
    }
    if (matches)
    { char left = i > 0 ? text[i - 1] : '\0';
     std::size_t right_index = i + code_upper.size();
     char right = right_index < text.size() ? text[right_index] : '\0';
     found = !IsAsciiAlnum(left) && !IsAsciiAlnum(right);
    }
   }
   return found;
  }
 }

// #R001: Matchycore traceability implementation coverage.
 CldrCurrencyMatcher::CldrCurrencyMatcher(const std::set<std::string> &tokens)
 { for (const std::string &token : tokens)
  { std::string clean = Strip(token);
   if (!clean.empty()) tokens_.insert(clean);
  }
  for (const std::string &token : tokens_)
  { if (IsThreeLetterAlpha(token)) codes_.push_back(Upper(token));
   else symbols_.push_back(token);
  }
  std::sort(codes_.begin(), codes_.end());
  std::sort(symbols_.begin(), symbols_.end(),
            [](const std::string &a, const std::string &b)
            { return a.size() != b.size() ? a.size() > b.size() : a < b; });
 }

// #R001: Matchycore traceability implementation coverage.
 bool CldrCurrencyMatcher::ContainsStandaloneCurrency(const std::string &text) const
 { bool matched = false;
  for (std::size_t i = 0; !matched && i < codes_.size(); i += 1) matched = CodeOccursStandalone(codes_[i], text);
  for (std::size_t i = 0; !matched && i < symbols_.size(); i += 1) matched = SymbolOccursStandalone(symbols_[i], text);
  return matched;
 }

// #R001: Matchycore traceability implementation coverage.
 CldrCurrenciesCache::CldrCurrenciesCache(const Settings &settings)
 { std::string path = settings.cldr_currencies_cache_path();
  const char *home = std::getenv("HOME");
  if (!path.empty() && path[0] == '~' && home != nullptr) path = std::string(home) + path.substr(1);
  if (path.empty() && home != nullptr) path = std::string(home) + "/.cache/matchy/cldr-currencies-en.json";
  cache_path_ = path;
  version_path_ = path + ".sha";
  timeout_seconds_ = settings.cldr_currencies_refresh_timeout_seconds() != 0
   ? settings.cldr_currencies_refresh_timeout_seconds() : 5;
 }

// #R001: Matchycore traceability implementation coverage.
 nlohmann::json CldrCurrenciesCache::Refresh()
 { std::string cached_version = Strip(ReadText(version_path_));
  nlohmann::json status = {{"cache_path", cache_path_}, {"version", cached_version}, {"updated", false}};
  try
  { std::string latest_version = LatestVersion();
   bool needs_download = latest_version != cached_version || !std::filesystem::exists(cache_path_);
   if (needs_download) WriteCache(DownloadBody(), latest_version);
   status = {{"cache_path", cache_path_}, {"version", latest_version}, {"updated", needs_download}};
  }
  catch (const std::exception &exc)
  { std::fprintf(stderr, "cldr currencies cache refresh skipped path=%s error=%s\n", cache_path_.c_str(), exc.what());
  }
  return status;
 }

// #R001: Matchycore traceability implementation coverage.
 CldrCurrencyMatcher CldrCurrenciesCache::CurrencyMatcher() const
 { return CldrCurrencyMatcher(CurrencyTokens());
 }

// #R001: Matchycore traceability implementation coverage.
 std::set<std::string> CldrCurrenciesCache::CurrencyTokens() const
 { std::set<std::string> tokens;
  std::string body = ReadText(cache_path_);
  if (!body.empty())
  { nlohmann::json payload = nlohmann::json::parse(body, nullptr, false);
   if (!payload.is_discarded()) tokens = ParseCurrencyTokens(payload);
   else std::fprintf(stderr, "cldr currencies cache parse skipped path=%s\n", cache_path_.c_str());
  }
  return tokens;
 }

 std::set<std::string> CldrCurrenciesCache::ParseCurrencyTokens(const nlohmann::json &payload)
 { std::set<std::string> tokens;
  // #R001: Locate main.en.numbers.currencies defensively.
  nlohmann::json currencies = nlohmann::json::object();
  if (payload.is_object() && payload.contains("main") && payload["main"].is_object())
  { const nlohmann::json &main = payload["main"];
   if (main.contains("en") && main["en"].is_object())
   { const nlohmann::json &en = main["en"];
    if (en.contains("numbers") && en["numbers"].is_object())
    { const nlohmann::json &numbers = en["numbers"];
     if (numbers.contains("currencies") && numbers["currencies"].is_object()) currencies = numbers["currencies"];
    }
   }
  }
  for (const auto &[code, entry] : currencies.items())
  { std::string clean_code = Upper(Strip(code));
   if (!clean_code.empty()) tokens.insert(clean_code);
   if (entry.is_object())
   { for (const auto &[key, raw_value] : entry.items())
    { if (key == "symbol" || key.rfind("symbol-alt-", 0) == 0)
     { std::string symbol = CleanSymbol(raw_value);
      if (!symbol.empty()) tokens.insert(symbol);
     }
    }
   }
  }
  return tokens;
 }

// #R001: Matchycore traceability implementation coverage.
 std::string CldrCurrenciesCache::LatestVersion() const
 { httplib::SSLClient client("api.github.com", 443);
  client.set_connection_timeout(timeout_seconds_, 0);
  client.set_read_timeout(timeout_seconds_, 0);
  httplib::Headers headers{{"Accept", "application/vnd.github+json"}, {"User-Agent", "matchycore"}};
  httplib::Result response = client.Get(
   "/repos/unicode-org/cldr-json/commits?sha=main&path=cldr-json/cldr-numbers-full/main/en/currencies.json&per_page=1",
   headers);
  if (!response || response->status >= 400) throw std::runtime_error("GitHub commits API request failed");
  nlohmann::json payload = nlohmann::json::parse(response->body, nullptr, false);
  std::string version;
  if (payload.is_array() && !payload.empty() && payload[0].is_object()) version = payload[0].value("sha", "");
  if (version.empty()) throw std::runtime_error("GitHub commits API did not return a file commit sha");
  return version;
 }

// #R001: Matchycore traceability implementation coverage.
 std::string CldrCurrenciesCache::DownloadBody() const
 { httplib::SSLClient client("raw.githubusercontent.com", 443);
  client.set_connection_timeout(timeout_seconds_, 0);
  client.set_read_timeout(timeout_seconds_, 0);
  httplib::Headers headers{{"User-Agent", "matchycore"}};
  httplib::Result response = client.Get("/unicode-org/cldr-json/main/cldr-json/cldr-numbers-full/main/en/currencies.json",
                                        headers);
  if (!response || response->status >= 400) throw std::runtime_error("CLDR currencies download failed");
  nlohmann::json parsed = nlohmann::json::parse(response->body, nullptr, false);
  if (parsed.is_discarded()) throw std::runtime_error("CLDR currencies payload is not valid JSON");
  return response->body;
 }

 // #R001: Persist payload and version metadata via temp-path replace with 660/770 permissions.
 void CldrCurrenciesCache::WriteCache(const std::string &body, const std::string &version) const
 { std::filesystem::path cache_path(cache_path_);
  std::vector<std::filesystem::path> missing_dirs;
  std::filesystem::path current = cache_path.parent_path();
  while (!current.empty() && !std::filesystem::exists(current))
  { missing_dirs.push_back(current);
   current = current.parent_path();
  }
  std::filesystem::create_directories(cache_path.parent_path());
  for (const std::filesystem::path &dir : missing_dirs) ::chmod(dir.c_str(), 0770);
  auto write_file = [](const std::filesystem::path &path, const std::string &content)
  { std::filesystem::path temp_path = path.parent_path() / ("." + path.filename().string() + ".tmp");
   std::ofstream out(temp_path, std::ios::binary | std::ios::trunc);
   out << content;
   out.close();
   ::chmod(temp_path.c_str(), 0660);
   std::filesystem::rename(temp_path, path);
   ::chmod(path.c_str(), 0660);
  };
  write_file(cache_path, body);
  write_file(std::filesystem::path(version_path_), version + "\n");
 }

// #R001: Matchycore traceability implementation coverage.
 std::string CldrCurrenciesCache::ReadText(const std::string &path)
 { std::ifstream in(path, std::ios::binary);
  std::string value;
  if (in)
  { std::string content((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
   value = content;
  }
  return value;
 }
}
