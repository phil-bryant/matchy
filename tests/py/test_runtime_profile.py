#R065: Python test lane coverage for gated runtime profiling instrumentation.

import pytest

from matchy.runtime_profile import _runtime_profile_enabled, _runtime_profile_log


def test_runtime_profile_is_gated_by_environment_flag(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    #R065-T01: Profiling is disabled by default and only emits a breadcrumb when MATCHY_RUNTIME_PROFILE=true.
    monkeypatch.delenv("MATCHY_RUNTIME_PROFILE", raising=False)
    disabled = _runtime_profile_enabled()
    _runtime_profile_log("phase-x", "detail-y")
    quiet = capsys.readouterr().out

    monkeypatch.setenv("MATCHY_RUNTIME_PROFILE", "true")
    enabled = _runtime_profile_enabled()
    _runtime_profile_log("phase-x", "detail-y")
    loud = capsys.readouterr().out

    assert disabled is False
    assert quiet == ""
    assert enabled is True
    assert "[matchy-runtime] phase-x | detail-y" in loud
