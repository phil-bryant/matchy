"""LIVE matchy integration tests (Teller DB + Mailcart).

This module is intentionally NOT under ``tests/py`` so the offline unit lane (t06) never collects it.
It is driven only by ``tests/t11_run_live_integration_tests.sh`` when MATCHY_LIVE_INTEGRATION=true and
the live dependencies are reachable. Every test here additionally guards itself with ``pytest.skip``
so a direct invocation against absent services soft-skips instead of producing a false failure.
"""
from __future__ import annotations

import os

import pytest


def _build_live_service():
    """Construct a real MatchService or skip when live dependencies are unavailable."""
    service = None
    try:
        from matchy.service import MatchService
        from matchy.settings import Settings

        service = MatchService(Settings())
    except Exception as exc:  # noqa: BLE001 - any construction failure means "deps not present here".
        pytest.skip(f"live matchy dependencies unavailable: {exc}")
    return service


def test_live_pending_batch_runs_end_to_end_against_real_services() -> None:
    """A real pending batch (or a configured transaction) returns well-formed, persisted results."""
    service = _build_live_service()
    configured_txn = os.environ.get("MATCHY_LIVE_TEST_TRANSACTION_ID", "").strip()
    if configured_txn:
        results = [service.match_transaction(transaction_id=configured_txn, trigger_source="manual")]
    else:
        results = service.match_pending_transactions(limit=1, lookback_days=30, trigger_source="manual")
    if not results:
        pytest.skip("no pending transactions available in the live Teller DB to match")
    row = results[0]
    assert "transaction_id" in row
    assert "selected_message_ids" in row
    assert isinstance(row["selected_message_ids"], list)
    # A real (non-skipped, non-errored) evaluation must persist a match_run the repository can read back.
    if row.get("skipped") is False and "error" not in row:
        assert row.get("run_id") is not None
