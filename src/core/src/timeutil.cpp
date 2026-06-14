#include "matchycore/timeutil.hpp"
#include <chrono>
#include <cstdio>

namespace matchycore::timeutil
{ namespace
 { // Howard Hinnant's days-from-civil algorithm.
// #R001: Matchycore traceability implementation coverage.
  long long DaysFromCivil(long long y, unsigned m, unsigned d)
  { y -= m <= 2;
   long long era = (y >= 0 ? y : y - 399) / 400;
   unsigned yoe = static_cast<unsigned>(y - era * 400);
   unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
   unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
   return era * 146097 + static_cast<long long>(doe) - 719468;
  }

// #R001: Matchycore traceability implementation coverage.
  void CivilFromDays(long long z, long long &y, unsigned &m, unsigned &d)
  { z += 719468;
   long long era = (z >= 0 ? z : z - 146096) / 146097;
   unsigned doe = static_cast<unsigned>(z - era * 146097);
   unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
   long long yr = static_cast<long long>(yoe) + era * 400;
   unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
   unsigned mp = (5 * doy + 2) / 153;
   d = doy - (153 * mp + 2) / 5 + 1;
   m = mp + (mp < 10 ? 3 : -9);
   y = yr + (m <= 2);
  }

// #R001: Matchycore traceability implementation coverage.
  bool ReadInt(const std::string &s, std::size_t pos, std::size_t count, long long &out)
  { bool ok = pos + count <= s.size();
   long long value = 0;
   for (std::size_t i = 0; ok && i < count; i += 1)
   { char c = s[pos + i];
    if (c < '0' || c > '9') ok = false;
    else value = value * 10 + (c - '0');
   }
   if (ok) out = value;
   return ok;
  }
 }

// #R001: Matchycore traceability implementation coverage.
 std::optional<TimePoint> ParseIso8601(const std::string &value)
 { std::optional<TimePoint> result;
  std::string s = value;
  std::size_t z_pos = s.find('Z');
  if (z_pos == std::string::npos) z_pos = s.find('z');
  if (z_pos != std::string::npos) s.replace(z_pos, std::string::npos, "+00:00");
  long long year = 0, month = 0, day = 0, hour = 0, minute = 0, second = 0, micros = 0, off_minutes = 0;
  bool ok = ReadInt(s, 0, 4, year) && s.size() > 4 && s[4] == '-' && ReadInt(s, 5, 2, month)
   && s.size() > 7 && s[7] == '-' && ReadInt(s, 8, 2, day);
  std::size_t pos = 10;
  if (ok && s.size() > pos && (s[pos] == 'T' || s[pos] == ' '))
  { pos += 1;
   ok = ReadInt(s, pos, 2, hour) && s.size() > pos + 2 && s[pos + 2] == ':' && ReadInt(s, pos + 3, 2, minute);
   pos += 5;
   if (ok && s.size() > pos && s[pos] == ':')
   { ok = ReadInt(s, pos + 1, 2, second);
    pos += 3;
   }
   if (ok && s.size() > pos && s[pos] == '.')
   { pos += 1;
    long long fraction = 0;
    std::size_t digits = 0;
    while (pos < s.size() && s[pos] >= '0' && s[pos] <= '9' && digits < 6)
    { fraction = fraction * 10 + (s[pos] - '0');
     digits += 1;
     pos += 1;
    }
    while (digits < 6)
    { fraction *= 10;
     digits += 1;
    }
    micros = fraction;
   }
   if (ok && s.size() > pos && (s[pos] == '+' || s[pos] == '-'))
   { long long off_h = 0, off_m = 0;
    bool negative = s[pos] == '-';
    ok = ReadInt(s, pos + 1, 2, off_h) && s.size() > pos + 3 && s[pos + 3] == ':' && ReadInt(s, pos + 4, 2, off_m);
    pos += 6;
    if (ok) off_minutes = (negative ? -1 : 1) * (off_h * 60 + off_m);
   }
   ok = ok && pos >= s.size();
  }
  else ok = ok && s.size() == 10;
  if (ok && month >= 1 && month <= 12 && day >= 1 && day <= 31)
  { long long days = DaysFromCivil(year, static_cast<unsigned>(month), static_cast<unsigned>(day));
   long long epoch_seconds = days * 86400 + hour * 3600 + minute * 60 + second - off_minutes * 60;
   result = TimePoint(std::chrono::duration_cast<TimePoint::duration>(
    std::chrono::seconds(epoch_seconds) + std::chrono::microseconds(micros)));
  }
  return result;
 }

 namespace
 { std::string FormatIsoImpl(TimePoint value, bool with_offset);
 }

// #R001: Matchycore traceability implementation coverage.
 std::string FormatIsoUtc(TimePoint value)
 { return FormatIsoImpl(value, true);
 }

// #R001: Matchycore traceability implementation coverage.
 std::string FormatIsoNaive(TimePoint value)
 { return FormatIsoImpl(value, false);
 }

 namespace
// #R001: Matchycore traceability implementation coverage.
 { std::string FormatIsoImpl(TimePoint value, bool with_offset)
 { auto since_epoch = std::chrono::duration_cast<std::chrono::microseconds>(value.time_since_epoch()).count();
  long long total_seconds = since_epoch / 1000000;
  long long micros = since_epoch % 1000000;
  if (micros < 0)
  { micros += 1000000;
   total_seconds -= 1;
  }
  long long days = total_seconds / 86400;
  long long seconds_of_day = total_seconds % 86400;
  if (seconds_of_day < 0)
  { seconds_of_day += 86400;
   days -= 1;
  }
  long long y = 0;
  unsigned m = 0, d = 0;
  CivilFromDays(days, y, m, d);
  char buffer[48];
  if (micros > 0)
   std::snprintf(buffer, sizeof(buffer), "%04lld-%02u-%02uT%02lld:%02lld:%02lld.%06lld", y, m, d,
                 seconds_of_day / 3600, (seconds_of_day / 60) % 60, seconds_of_day % 60, micros);
  else
   std::snprintf(buffer, sizeof(buffer), "%04lld-%02u-%02uT%02lld:%02lld:%02lld", y, m, d,
                 seconds_of_day / 3600, (seconds_of_day / 60) % 60, seconds_of_day % 60);
  return std::string(buffer) + (with_offset ? "+00:00" : "");
 }
 }

// #R001: Matchycore traceability implementation coverage.
 std::string UtcDateString(TimePoint value, long long day_offset)
 { long long total_seconds = std::chrono::duration_cast<std::chrono::seconds>(value.time_since_epoch()).count();
  long long days = total_seconds / 86400;
  if (total_seconds % 86400 < 0) days -= 1;
  days += day_offset;
  long long y = 0;
  unsigned m = 0, d = 0;
  CivilFromDays(days, y, m, d);
  char buffer[16];
  std::snprintf(buffer, sizeof(buffer), "%04lld-%02u-%02u", y, m, d);
  return std::string(buffer);
 }
}
