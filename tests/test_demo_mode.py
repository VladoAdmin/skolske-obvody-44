"""
Demo-mode tests — when a complete demo input row is present, each checker must
emit a DECISIVE, high-confidence (>=0.90) verdict flagged is_mock, AND the
real-data path must stay honest when no demo row exists.

WHY these matter:
  * The product demo requires ZERO non-decisive states and conf/compl >= 0.90 on
    every condition. A checker that silently drops back to INSUFFICIENT_DATA /
    INCOMPLETE / NO_SIGNAL under demo input would break the demo contract.
  * Demo verdicts MUST be is_mock=True so the UI badges them DEMO (legal honesty).
  * compose_color must turn an indicator FAIL (Pa/Pc/Pd) into ORANGE — never green,
    never RED — so a real §44 risk is visible without overstating legal status.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.constants import V, Color
from engine.compose import compose_color
from engine.verdict import Verdict

_D = {
    "id": "00000000-0000-0000-0000-000000000001",
    "school_id": "00000000-0000-0000-0000-0000000000aa",
    "school_name": "ZŠ Test",
    "school_type": "ZS",
    "teaching_language": "SK",
    "municipality_id": "00000000-0000-0000-0000-0000000000mm",
    "geometry_confidence": "high",
}

HIGH = 0.90


def _decisive(v: Verdict, expected_value: str):
    assert v.value == expected_value, f"{v.condition_code}: {v.value} != {expected_value}"
    assert v.confidence >= HIGH, f"{v.condition_code} confidence {v.confidence} < 0.90"
    assert v.data_completeness >= HIGH, f"{v.condition_code} completeness {v.data_completeness} < 0.90"
    assert v.is_mock is True, f"{v.condition_code} demo verdict must be is_mock"


# --------------------------------------------------------------------------- S1
def test_s1_demo_wrong_district_fails():
    import engine.c_s1 as c
    demo = {"s1_total_addresses": 820, "s1_uncovered": 0, "s1_wrong_district": 14}
    with mock.patch.object(c, "get_demo_input", return_value=demo):
        _decisive(c.check_s1(_D, [_D], _D["municipality_id"]), V.FAIL)


def test_s1_demo_clean_passes():
    import engine.c_s1 as c
    demo = {"s1_total_addresses": 500, "s1_uncovered": 0, "s1_wrong_district": 0}
    with mock.patch.object(c, "get_demo_input", return_value=demo):
        _decisive(c.check_s1(_D, [_D], _D["municipality_id"]), V.PASS)


# --------------------------------------------------------------------------- S3
def test_s3_demo_two_schools_fail():
    import engine.c_s3 as c
    with mock.patch.object(c, "get_demo_input", return_value={"s3_school_count": 2}):
        _decisive(c.check_s3(_D), V.FAIL)


def test_s3_demo_one_school_pass():
    import engine.c_s3 as c
    with mock.patch.object(c, "get_demo_input", return_value={"s3_school_count": 1}):
        _decisive(c.check_s3(_D), V.PASS)


# --------------------------------------------------------------------------- Pa
def test_pa_demo_over_2km_fail():
    import engine.c_pa as c
    with mock.patch.object(c, "get_demo_input", return_value={"pa_max_distance_m": 2480}):
        _decisive(c.check_pa(_D), V.FAIL)


def test_pa_demo_within_pass():
    import engine.c_pa as c
    with mock.patch.object(c, "get_demo_input", return_value={"pa_max_distance_m": 900}):
        _decisive(c.check_pa(_D), V.PASS)


# --------------------------------------------------------------------------- Pc
def test_pc_demo_two_transfers_fail_and_not_illustrative():
    import engine.c_pc as c
    demo = {"pc_transfers": 2, "pc_total_minutes": 41}
    with mock.patch.object(c, "get_demo_input", return_value=demo):
        v = c.check_pc(_D)
    _decisive(v, V.FAIL)
    # In demo mode Pc is a REAL indicator so it can push the semafor to ORANGE.
    assert v.is_illustrative is False


def test_pc_demo_one_transfer_pass():
    import engine.c_pc as c
    with mock.patch.object(c, "get_demo_input", return_value={"pc_transfers": 1, "pc_total_minutes": 16}):
        _decisive(c.check_pc(_D), V.PASS)


# --------------------------------------------------------------------------- Pd
def test_pd_demo_barrier_fail_not_language():
    import engine.c_pd as c
    demo = {"pd_barrier": True, "pd_barrier_kind": "železnica bez podchodu"}
    with mock.patch.object(c, "get_demo_input", return_value=demo):
        v = c.check_pd(_D)
    _decisive(v, V.FAIL)
    text = v.evidence_text.lower()
    assert "bariér" in text or "železnic" in text
    assert "menšin" not in text and "vyučovac" not in text


def test_pd_demo_no_barrier_pass():
    import engine.c_pd as c
    with mock.patch.object(c, "get_demo_input", return_value={"pd_barrier": False}):
        _decisive(c.check_pd(_D), V.PASS)


# ------------------------------------------------------------------------- JAZYK
def test_jazyk_demo_minority_signal():
    """A minority teaching language is a decisive SIGNAL (podnet mimo § 44)."""
    import engine.c_lang as c
    with mock.patch.object(c, "get_demo_input", return_value={"jazyk_language": "HU"}):
        v = c.check_lang(_D)
    _decisive(v, V.SIGNAL)
    assert "menšin" in v.evidence_text.lower()


def test_jazyk_demo_slovak_is_evaluated_never_not_evaluated():
    """
    Item 4 (owner explicit): in demo mode JAZYK for a Slovak-teaching school must
    be a DECISIVE evaluated state (NO_SIGNAL — "bez jazykového podnetu"), NEVER
    the literal NOT_EVALUATED. Stays is_mock + outside the semafor.
    """
    import engine.c_lang as c
    with mock.patch.object(c, "get_demo_input", return_value={"jazyk_language": None}):
        v = c.check_lang(_D)
    assert v.value == V.NO_SIGNAL, f"expected NO_SIGNAL, got {v.value}"
    assert v.value != V.NOT_EVALUATED
    assert v.confidence >= HIGH and v.data_completeness >= HIGH
    assert v.is_mock is True
    assert "slovenčin" in v.evidence_text.lower()


# --------------------------------------------------------------------------- Pe
def test_pe_demo_signal():
    import engine.c_pe as c
    with mock.patch.object(c, "get_demo_input", return_value={"pe_mrk_signal": True}):
        _decisive(c.check_pe(_D, _D["municipality_id"]), V.SIGNAL)


def test_pe_demo_no_issue_is_pass_not_no_signal():
    import engine.c_pe as c
    with mock.patch.object(c, "get_demo_input", return_value={"pe_mrk_signal": False}):
        # decisive "all good" for a signal condition must read PASS, not NO_SIGNAL
        _decisive(c.check_pe(_D, _D["municipality_id"]), V.PASS)


# --------------------------------------------------------------------------- Pf
def test_pf_demo_overcrowd_signal():
    import engine.c_pf as c
    demo = {"pf_capacity": 560, "pf_enrolment": 712}
    with mock.patch.object(c, "get_demo_input", return_value=demo):
        _decisive(c.check_pf(_D), V.SIGNAL)


def test_pf_demo_within_capacity_pass():
    import engine.c_pf as c
    demo = {"pf_capacity": 600, "pf_enrolment": 450}
    with mock.patch.object(c, "get_demo_input", return_value=demo):
        _decisive(c.check_pf(_D), V.PASS)


# ----------------------------------------------------------------------- compose
def test_indicator_fail_pushes_orange_not_green_not_red():
    """An indicator FAIL must be ORANGE: visible risk, but legal status (Š1–Š3)
    stays clean so it is never RED."""
    verdicts = {
        "S1": Verdict(_D["id"], "S1", V.PASS, 0.95, 0.95, {}, {}),
        "S2": Verdict(_D["id"], "S2", V.PASS, 0.95, 0.95, {}, {}),
        "S3": Verdict(_D["id"], "S3", V.PASS, 0.95, 0.95, {}, {}),
        "Pd": Verdict(_D["id"], "Pd", V.FAIL, 0.95, 0.95, {}, {}),
    }
    out = compose_color(verdicts)
    assert out["color"] == Color.ORANGE


def test_legal_fail_is_red_regardless_of_indicators():
    verdicts = {
        "S2": Verdict(_D["id"], "S2", V.FAIL, 0.95, 0.95, {}, {}),
        "Pd": Verdict(_D["id"], "Pd", V.PASS, 0.95, 0.95, {}, {}),
    }
    assert compose_color(verdicts)["color"] == Color.RED


# ----------------------------------------------------------------- demo-tag strip
def test_evidence_strips_inline_demo_tags():
    """
    Item 7: the stored (UI-facing) evidence_text must NOT carry inline
    [DEMO]/Ukážkové-dáta notices — the single top banner is the only demo notice.
    The is_mock flag still carries the demo status internally.
    """
    from engine.verdict import strip_demo_tags
    v = Verdict(_D["id"], "S1", V.FAIL, 0.95, 0.95, {}, {},
                evidence_text="FAIL [DEMO]: 14 adries v zlom obvode. Ukážkové dáta.",
                is_mock=True)
    rec = v.to_db_record()
    assert "[DEMO" not in rec["evidence_text"]
    assert "Ukážkov" not in rec["evidence_text"]
    assert rec["evidence_text"].startswith("FAIL:")
    assert rec["is_mock"] is True
    # helper is idempotent
    assert strip_demo_tags(rec["evidence_text"]) == rec["evidence_text"]
