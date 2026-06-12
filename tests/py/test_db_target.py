#R030: Python test lane coverage for backend target detection.
#R035: Python test lane coverage for owned-schema SQL rendering.
#R040: Python test lane coverage for backend-aware parameter fragments.

from datetime import date, datetime

import pytest

from matchy import db_target


def test_target_detection_defaults_to_postgres_when_profile_unresolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    #R030-T01: Detection returns false when profile resolution raises and true for sqlite profiles.
    monkeypatch.setattr(
        "teller.teller_db_profile.resolve_profile",
        lambda: (_ for _ in ()).throw(RuntimeError("no profile")),
    )
    assert db_target._is_sqlite_target() is False

    class _Profile:
        target = "sqlite"

    monkeypatch.setattr("teller.teller_db_profile.resolve_profile", lambda: _Profile())
    assert db_target._is_sqlite_target() is True


def test_owned_schema_sql_renders_per_target(monkeypatch: pytest.MonkeyPatch) -> None:
    #R035-T01: Owned-schema references rewrite on sqlite and pass through on postgres.
    sql = "SELECT 1 FROM matchy.transaction_email_match JOIN classy.nys_snw_category USING (x)"
    monkeypatch.setattr(db_target, "_IS_SQLITE", False)
    assert db_target.sql_for_target(sql) == sql
    monkeypatch.setattr(db_target, "_IS_SQLITE", True)
    rewritten = db_target.sql_for_target(sql)
    assert "teller.matchy_transaction_email_match" in rewritten
    assert "teller.classy_nys_snw_category" in rewritten


def test_teller_transaction_is_quoted_on_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    #R035-T02: teller.transaction references are quoted on the sqlite target.
    sql = "SELECT 1 FROM teller.transaction tt JOIN teller.transaction_details td ON 1=1"
    monkeypatch.setattr(db_target, "_IS_SQLITE", True)
    rewritten = db_target.sql_for_target(sql)
    assert 'teller."transaction" tt' in rewritten
    assert "teller.transaction_details td" in rewritten  # longer names untouched
    monkeypatch.setattr(db_target, "_IS_SQLITE", False)
    assert db_target.sql_for_target(sql) == sql


def test_parameter_fragments_vary_by_target(monkeypatch: pytest.MonkeyPatch) -> None:
    #R040-T01: jsonb/timestamp fragments and datetime normalization vary by target.
    monkeypatch.setattr(db_target, "_IS_SQLITE", False)
    assert db_target.jsonb_param("payload") == "CAST(:payload AS jsonb)"
    stamp = datetime(2026, 6, 12, 13, 30, 5)
    assert db_target.bind_timestamp(stamp) is stamp

    monkeypatch.setattr(db_target, "_IS_SQLITE", True)
    assert db_target.jsonb_param("payload") == ":payload"
    assert db_target.bind_timestamp(stamp) == "2026-06-12 13:30:05"

    assert db_target.as_datetime(None) is None
    assert db_target.as_datetime(stamp) is stamp
    assert db_target.as_datetime(date(2026, 6, 12)) == datetime(2026, 6, 12)
    assert db_target.as_datetime("2026-06-12") == datetime(2026, 6, 12)
    assert db_target.as_datetime("2026-06-12 13:30:05") == datetime(2026, 6, 12, 13, 30, 5)
    assert db_target.as_datetime("2026-06-12T13:30:05.123456") == datetime(2026, 6, 12, 13, 30, 5, 123456)
    assert db_target.as_datetime("not-a-date") is None
