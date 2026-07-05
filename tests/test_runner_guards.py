"""
Runner-level guards — Step 2 Sprint 2.

WHY these matter:
  * `_assert_red_only_structural` is the last line of defence proving a RED
    district is always driven by a real Š1/Š2/Š3 FAIL. The Š2 address-overlap
    demo (0041) is the first scenario that legitimately drives RED through a
    demo-seeded row — these tests prove the guard accepts that (S2 is a legal
    condition) and still rejects a non-structural condition trying to cause RED.
  * `_write_finding`'s severity must mirror the semafor's RED/ORANGE/signal
    discipline: a legal FAIL is worse than an indicator FAIL/RISK, which is
    worse than an analytical SIGNAL, which is worse than the non-§44 JAZYK
    podnet. Collapsing all FAIL values to the same severity (as before this
    sprint) made an indicator finding look as severe as a structural violation
    in the findings register.
  * `refresh_demo_mode()` proves the lru_cache-backed demo_mode gate can be
    forced to re-read the DB — the fix for the Sprint 1 review's "mid-process
    toggle invisible" finding.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.constants import V
from engine.verdict import Verdict

_DID = "00000000-0000-0000-0000-000000000001"


def _v(code: str, value: str) -> Verdict:
    return Verdict(
        district_id=_DID,
        condition_code=code,
        value=value,
        confidence=0.9,
        data_completeness=0.9,
        provenance={},
        methodology={},
    )


# --------------------------------------------------------- RedOnlyStructuralError
def test_s2_demo_fail_is_legitimate_red_and_does_not_raise():
    """The Š2 address-overlap demo FAIL is a real legal condition — RED driven
    only by S2=FAIL must NOT raise, even though the FAIL originates from a
    demo-seeded house_geocodes row (is_mock=True on the Verdict)."""
    import engine.runner as r

    verdicts = {
        "S1": _v("S1", V.PASS),
        "S2": _v("S2", V.FAIL),
        "S3": _v("S3", V.PASS),
        "Pa": _v("Pa", V.PASS),
    }
    r._assert_red_only_structural("Test district", "RED", verdicts)  # must not raise


def test_red_with_no_structural_fail_raises():
    """Regression guard: if RED is ever computed without an S1/S2/S3 FAIL, the
    guard must fail loudly rather than let a non-structural condition silently
    colour a district red."""
    import engine.runner as r

    verdicts = {
        "S1": _v("S1", V.PASS),
        "S2": _v("S2", V.PASS),
        "S3": _v("S3", V.PASS),
        "Pa": _v("Pa", V.FAIL),
    }
    try:
        r._assert_red_only_structural("Test district", "RED", verdicts)
        assert False, "expected RedOnlyStructuralError"
    except r.RedOnlyStructuralError:
        pass


def test_red_with_indicator_fail_alongside_structural_fail_raises():
    """Even when a real S-FAIL is present, an indicator FAIL must not be able
    to piggy-back into RED attribution beyond the legal condition itself —
    the guard only tolerates non-structural FAILs that are indicator/signal
    conditions (which never independently drive RED); anything else must raise."""
    import engine.runner as r

    verdicts = {
        "S1": _v("S1", V.FAIL),
        "JAZYK": _v("JAZYK", V.FAIL),  # JAZYK should never even reach FAIL, but prove the guard rejects it
    }
    try:
        r._assert_red_only_structural("Test district", "RED", verdicts)
        assert False, "expected RedOnlyStructuralError for a non-structural FAIL driver"
    except r.RedOnlyStructuralError:
        pass


# --------------------------------------------------------------- severity tiers
def _captured_severity(condition_code: str, value: str) -> str:
    """Run _write_finding with exec_sql mocked, return the severity literal
    embedded in the generated INSERT SQL."""
    import engine.runner as r

    captured = {}

    def fake_exec_sql(sql: str):
        captured["sql"] = sql
        return {"ok": True}

    with mock.patch.object(r, "exec_sql", side_effect=fake_exec_sql):
        written = r._write_finding(
            "verdict-id", _DID, "mun-id", condition_code, value, "evidence"
        )
    assert written is True, f"{condition_code}/{value} should have written a finding"
    sql = captured["sql"]
    for sev in ("critical", "high", "medium", "low", "info"):
        if f"'{sev}'" in sql:
            return sev
    raise AssertionError(f"no recognised severity literal found in SQL: {sql}")


def test_legal_fail_is_critical_severity():
    assert _captured_severity("S2", V.FAIL) == "critical"


def test_indicator_fail_is_high_not_critical():
    """An indicator FAIL/RISK (Pa-Pd) must never reach 'critical' — that would
    make it look as severe as a legal S1/S2/S3 violation in the register."""
    assert _captured_severity("Pa", V.FAIL) == "high"
    assert _captured_severity("Pd", V.FAIL) == "high"


def test_indicator_risk_is_high():
    assert _captured_severity("Pb", V.RISK) == "high"


def test_signal_is_medium_not_critical_or_high():
    assert _captured_severity("Pe", V.SIGNAL) == "medium"
    assert _captured_severity("Pf", V.SIGNAL) == "medium"


def test_jazyk_signal_is_low_never_red_tier():
    """JAZYK is a podnet nad rámec § 44 — it must never be 'critical' or
    'high' in the findings register, matching 'language never red'."""
    assert _captured_severity("JAZYK", V.SIGNAL) == "low"


# ------------------------------------------------------------- refresh_demo_mode
def test_refresh_demo_mode_clears_stale_flag_value():
    """Proves the Sprint 1 review fix: without refresh_demo_mode(), a
    mid-process demo_mode_flag toggle is invisible because of lru_cache.
    Calling refresh_demo_mode() forces the next read to re-hit the DB."""
    import engine.demo_inputs as di

    di.refresh_demo_mode()
    calls = {"n": 0}

    def fake_query_sql(sql: str):
        calls["n"] += 1
        # First read: disabled. After refresh: enabled.
        return [{"on": calls["n"] > 1}]

    with mock.patch.object(di, "query_sql", side_effect=fake_query_sql):
        assert di.demo_mode_enabled() is False
        assert di.demo_mode_enabled() is False, "cached — must not re-query"
        assert calls["n"] == 1

        di.refresh_demo_mode()
        assert di.demo_mode_enabled() is True
        assert calls["n"] == 2
    di.refresh_demo_mode()
