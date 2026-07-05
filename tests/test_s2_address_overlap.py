"""
Š2 address-overlap tests — Step 2 Sprint 1.

WHY these matter:
  * streets-pivot (2026-06-28) retired the polygon-based overlap test. The ONLY
    structural overlap concept left is the SAME FULL ADDRESS (street + house
    number) claimed by two districts — a shared/boundary STREET alone is not a
    finding. These tests assert the SQL construction actually requires
    house_number equality (not just street), so a future edit can't silently
    regress to street-only matching.
  * Demo addresses (house_geocodes.is_demo=TRUE) must never affect a live/prod
    Š2 verdict just by existing in the table — c_s2 excludes them from the
    query unless demo_mode_enabled() is True. These tests prove that gate by
    inspecting the actual SQL sent, and prove a demo-caused FAIL is flagged
    is_mock=True while a real-data FAIL stays is_mock=False.

Run: python3 -m pytest tests/test_s2_address_overlap.py -v
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.constants import V

_D = {
    "id": "00000000-0000-0000-0000-000000000001",
    "school_type": "ZS",
    "teaching_language": "SK",
}
_MUN = "00000000-0000-0000-0000-0000000000mm"


def _run(overlap_rows, demo_enabled):
    import engine.c_s2 as c
    captured: list[str] = []

    def fake_query_sql(sql: str):
        captured.append(sql)
        return overlap_rows

    with mock.patch.object(c, "demo_mode_enabled", return_value=demo_enabled), \
         mock.patch.object(c, "query_sql", side_effect=fake_query_sql):
        v = c.check_s2(_D, [_D], _MUN)
    return v, captured[0]


# ------------------------------------------------------------- SQL construction
def test_overlap_query_requires_house_number_equality_not_just_street():
    """The join must key on BOTH street and house_number — proves the overlap
    concept is address-based, not street-based (a shared street alone must not
    be matchable by this query)."""
    _, sql = _run([], demo_enabled=False)
    norm = " ".join(sql.split()).lower()
    assert "trim(h1.house_number) = trim(h2.house_number)" in norm
    assert "lower(trim(h1.street)) = lower(trim(h2.street))" in norm


def test_query_excludes_demo_rows_when_demo_mode_disabled():
    _, sql = _run([], demo_enabled=False)
    norm = " ".join(sql.split()).lower()
    assert "h1.is_demo is not true" in norm
    assert "h2.is_demo is not true" in norm


def test_query_includes_demo_rows_when_demo_mode_enabled():
    _, sql = _run([], demo_enabled=True)
    norm = " ".join(sql.split()).lower()
    assert "is_demo is not true" not in norm


# ------------------------------------------------------------------ PASS path
def test_no_overlap_rows_is_pass():
    v, _ = _run([], demo_enabled=False)
    assert v.value == V.PASS
    assert v.is_mock is False


# ------------------------------------------------------------ real FAIL path
def test_real_overlap_fails_and_is_not_mock():
    rows = [{"partner_id": "p1", "partner_name": "Susedný obvod", "shared_addresses": 1, "any_demo": False}]
    v, _ = _run(rows, demo_enabled=False)
    assert v.value == V.FAIL
    assert v.is_mock is False
    assert v.confidence == 0.7
    text = v.evidence_text.lower()
    assert "adresa" in text or "adries" in text
    assert "susedný obvod" in text


# ------------------------------------------------------------ demo FAIL path
def test_demo_overlap_fails_and_is_flagged_mock():
    """A FAIL caused by demo-flagged addresses (only reachable when demo mode
    is on, per the exclusion test above) must be flagged is_mock=True and
    carry demo-tier confidence, exactly like every other demo-driven verdict."""
    rows = [{"partner_id": "p1", "partner_name": "Sibírska", "shared_addresses": 1, "any_demo": True}]
    v, _ = _run(rows, demo_enabled=True)
    assert v.value == V.FAIL
    assert v.is_mock is True
    assert v.confidence >= 0.90
    assert v.data_completeness >= 0.90
    assert v.provenance["demo"] is True


def test_demo_tag_stripped_from_stored_evidence():
    rows = [{"partner_id": "p1", "partner_name": "Sibírska", "shared_addresses": 1, "any_demo": True}]
    v, _ = _run(rows, demo_enabled=True)
    rec = v.to_db_record()
    assert "Ukážkov" not in rec["evidence_text"]
    assert rec["is_mock"] is True
