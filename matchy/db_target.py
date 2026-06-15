"""Active-backend SQL adaptation for matchy (profile-driven, ADR-0006).

Matchy authors SQL with canonical schema-qualified names (``matchy.<t>``,
``teller.<t>``) and adapts at runtime to the active teller DB profile target:

- PostgreSQL: SQL passes through unchanged (enum/jsonb casts included).
- SQLite/SQLCipher: owned schemas map to prefixed mirror tables in the attached
  ``teller`` schema (``matchy.<t>`` -> ``teller.matchy_<t>``), the reserved word
  ``teller.transaction`` is quoted, and jsonb casts collapse to plain text.

#R030: Resolve the active backend target from the teller DB profile chain.
#R035: Render owned-schema SQL against SQLite prefixed mirror tables.
#R040: Provide jsonb-cast and timestamp parameter fragments per backend target.
"""

from __future__ import annotations

import re
from datetime import date, datetime

_OWNED_SQLITE_PREFIXES = {
    "classy": "classy_",
    "matchy": "matchy_",
}
_OWNED_SCHEMA_TABLE_PATTERN = re.compile(r"\b(classy|matchy)\.([A-Za-z_][A-Za-z0-9_]*)\b")
_TELLER_TRANSACTION_PATTERN = re.compile(r"\bteller\.transaction\b")


#R030: Shard-owned helper resolves the active backend target once per process.
def _is_sqlite_target() -> bool:
    try:
        from teller.teller_db_profile import resolve_profile

        return resolve_profile().target == "sqlite"
    except Exception:  # noqa: BLE001 - missing/invalid profile means postgres-era default
        return False


_IS_SQLITE = _is_sqlite_target()


#R030: Expose the resolved target for service/runtime call sites.
def is_sqlite() -> bool:
    return _IS_SQLITE


#R035: Render owned-schema SQL against the active backend target.
def sql_for_target(sql_text: str) -> str:
    if not _IS_SQLITE:
        return sql_text

    #R035: Rewrite owned-schema references to SQLite mirror table names.
    def _sqlite_ref(match: re.Match[str]) -> str:
        schema_name = match.group(1)
        table_name = match.group(2)
        return f"teller.{_OWNED_SQLITE_PREFIXES[schema_name]}{table_name}"

    rewritten = _OWNED_SCHEMA_TABLE_PATTERN.sub(_sqlite_ref, sql_text)
    # ``transaction`` is a reserved word; current SQLite parsers reject it
    # unquoted after a schema prefix.
    return _TELLER_TRANSACTION_PATTERN.sub('teller."transaction"', rewritten)


#R040: jsonb parameters are Postgres-typed; SQLite stores JSON as plain text.
def jsonb_param(param_name: str) -> str:
    if _IS_SQLITE:
        return f":{param_name}"
    return f"CAST(:{param_name} AS jsonb)"


#R040: Bind timestamps as ISO text on SQLite (parity with CURRENT_TIMESTAMP format).
def bind_timestamp(value: datetime):
    if _IS_SQLITE:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


#R040: Normalize date/timestamp column values read from either backend.
def as_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text_value = str(value).strip()
    if not text_value:
        return None
    normalized = text_value.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None
