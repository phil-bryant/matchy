#pragma once
#include <optional>
#include <string>
#include "matchycore/models.hpp"

// Datetime helpers mirroring the Python reference (datetime.fromisoformat / isoformat with UTC).
namespace matchycore::timeutil
{ // Parse ISO 8601 ("2024-06-01T12:00:00[.ffffff][Z|+HH:MM]" or date-only); naive values are treated as UTC.
 // #R001: Matchycore traceability requirement anchor for time utilities.
 std::optional<TimePoint> ParseIso8601(const std::string &value);

 // Python datetime(..., tzinfo=utc).isoformat(): microseconds included only when non-zero, "+00:00" suffix.
 std::string FormatIsoUtc(TimePoint value);

 // Python naive datetime isoformat(): same shape without the offset suffix.
 std::string FormatIsoNaive(TimePoint value);

 // "YYYY-MM-DD" of the UTC calendar date, optionally shifted by whole days.
 std::string UtcDateString(TimePoint value, long long day_offset = 0);
}
