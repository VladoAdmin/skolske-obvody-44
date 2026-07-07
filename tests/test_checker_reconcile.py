"""
Reconciliation tests — each checker must compute the meaning of its labels.ts label.

labels.ts (canonical):
  Pa = "Vzdialenosť ZŠ 1. stupeň ≤ 2 km"  (air-line distance address→school)
  Pd = "Bariéry (cesty, koľaje)"          (physical barriers; NOT language)
  Pe = "Sociálny kontext (Atlas MRK)"     (locality MRK signal; NOT blanket area)
  Pf = "Demografia detí"                  (children/enrolment vs school capacity)

These tests encode WHY the verdict matters: a verdict whose evidence text or value
semantics drift back to the OLD meaning (capacity under Pa, language under Pd,
ŠVVP under Pf, blanket area under Pe) must fail here.

Run: python3 -m pytest tests/test_checker_reconcile.py -v
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.constants import V

_D = {
    "id": "00000000-0000-0000-0000-000000000001",
    "school_id": "00000000-0000-0000-0000-0000000000aa",
    "school_name": "ZŠ Test",
    "school_type": "ZS",
    "municipality_id": "00000000-0000-0000-0000-0000000000mm",
    "geometry_confidence": "high",
}


# --------------------------------------------------------------------------- Pa
class TestPaIsAirlineDistance:
    """Pa must compute air-line distance address→school, FAIL when any > 2 km."""

    def test_far_address_fails(self):
        import engine.c_pa as c_pa
        rows = [
            {"street": "Ďaleká", "house_number": "9", "is_demo": False,
             "dist_m": 2450.0, "lat": 49.0, "lon": 21.2},
            {"street": "Blízka", "house_number": "1", "is_demo": False,
             "dist_m": 300.0, "lat": 49.0, "lon": 21.2},
        ]
        with mock.patch.object(c_pa, "query_sql", return_value=rows):
            v = c_pa.check_pa(_D)
        assert v.condition_code == "Pa"
        assert v.value == V.FAIL, "address > 2 km must FAIL"
        assert "2 km" in v.evidence_text or "2450" in v.evidence_text
        # must NOT be about capacity / EDUZBER occupancy (old meaning)
        assert "kapacit" not in v.evidence_text.lower()
        assert "obsadenosť" not in v.evidence_text.lower()

    def test_all_close_passes(self):
        import engine.c_pa as c_pa
        rows = [
            {"street": "A", "house_number": str(i), "is_demo": False,
             "dist_m": 400.0 + i, "lat": 49.0, "lon": 21.2}
            for i in range(5)
        ]
        with mock.patch.object(c_pa, "query_sql", return_value=rows):
            v = c_pa.check_pa(_D)
        assert v.value == V.PASS

    def test_too_few_points_insufficient(self):
        import engine.c_pa as c_pa
        rows = [{"street": "A", "house_number": "1", "is_demo": False,
                 "dist_m": 500.0, "lat": 49.0, "lon": 21.2}]
        with mock.patch.object(c_pa, "query_sql", return_value=rows):
            v = c_pa.check_pa(_D)
        assert v.value == V.INSUFFICIENT_DATA

    def test_demo_far_address_flags_mock(self):
        import engine.c_pa as c_pa
        rows = [{"street": "Demo", "house_number": "1", "is_demo": True,
                 "dist_m": 3000.0, "lat": 49.0, "lon": 21.2}]
        with mock.patch.object(c_pa, "query_sql", return_value=rows):
            v = c_pa.check_pa(_D)
        assert v.value == V.FAIL
        assert v.is_mock is True, "demo-decided FAIL must be flagged is_mock"


# --------------------------------------------------------------------------- Pd
class TestPdIsBarriersNotLanguage:
    """Pd must be physical barriers, evaluated from the barrier INPUT table
    (VLA-20: the "nedostatočné dáta" state was removed — the table is always
    seeded, so Pd always has an input). It must NEVER emit language/teaching-
    language content (old meaning)."""

    def test_demo_barrier_crossing_fails_is_mock_and_not_language(self):
        import engine.c_pd as c_pd
        crossing = [{"kind": "railway",
                     "name": "Železničná trať bez podchodu (DEMO — fiktívna bariéra)",
                     "is_demo": True}]
        dataset = [{"n": 1, "any_demo": True}]
        with mock.patch.object(c_pd, "get_demo_input", return_value=None), \
             mock.patch.object(c_pd, "query_sql", side_effect=[crossing, dataset]):
            v = c_pd.check_pd(_D)
        assert v.condition_code == "Pd"
        assert v.value == V.FAIL
        # Fabricated barrier ⇒ verdict must carry the mock flag (DEMO badge,
        # mock-never-RED gatekeeping: indicator FAIL maps to ORANGE).
        assert v.is_mock is True
        text = v.evidence_text.lower()
        assert "bariér" in text
        # language vocabulary absent (the bug we are fixing)
        assert "jazyk" not in text or "netýka jazyka" in text
        assert "menšin" not in text
        assert "vyučovac" not in text

    def test_no_crossing_with_demo_dataset_passes_is_mock(self):
        import engine.c_pd as c_pd
        with mock.patch.object(c_pd, "get_demo_input", return_value=None), \
             mock.patch.object(c_pd, "query_sql",
                               side_effect=[[], [{"n": 1, "any_demo": True}]]):
            v = c_pd.check_pd(_D)
        assert v.value == V.PASS
        assert v.is_mock is True

    def test_empty_barrier_table_guard_insufficient(self):
        """Unreachable in production (0045 seeds the table) — but the guard
        must stay honest rather than invent a PASS from no input at all."""
        import engine.c_pd as c_pd
        with mock.patch.object(c_pd, "get_demo_input", return_value=None), \
             mock.patch.object(c_pd, "query_sql",
                               side_effect=[[], [{"n": 0, "any_demo": None}]]):
            v = c_pd.check_pd(_D)
        assert v.value == V.INSUFFICIENT_DATA


# --------------------------------------------------------------------------- Pf
class TestPfIsDemografiaCapacity:
    """Pf must compare enrolment vs school capacity; SIGNAL on overcrowding.
    It must NEVER be about ŠVVP (old meaning)."""

    def test_overcrowded_signals(self):
        import engine.c_pf as c_pf
        rows = [{"capacity": 560, "student_count": 712, "cap_is_demo": True}]
        with mock.patch.object(c_pf, "query_sql", return_value=rows):
            v = c_pf.check_pf(_D)
        assert v.condition_code == "Pf"
        assert v.value == V.SIGNAL
        assert "712" in v.evidence_text and "560" in v.evidence_text
        assert "švvp" not in v.evidence_text.lower()
        assert v.is_mock is True

    def test_within_capacity_no_signal(self):
        import engine.c_pf as c_pf
        rows = [{"capacity": 600, "student_count": 480, "cap_is_demo": False}]
        with mock.patch.object(c_pf, "query_sql", return_value=rows):
            v = c_pf.check_pf(_D)
        assert v.value == V.NO_SIGNAL

    def test_missing_capacity_not_evaluated(self):
        import engine.c_pf as c_pf
        rows = [{"capacity": None, "student_count": None, "cap_is_demo": False}]
        with mock.patch.object(c_pf, "query_sql", return_value=rows):
            v = c_pf.check_pf(_D)
        assert v.value == V.NOT_EVALUATED
        assert "švvp" not in v.evidence_text.lower()


# --------------------------------------------------------------------------- Pe
class TestPeIsLocalityNotBlanketArea:
    """Pe signal must come from MRK locality buildings, not a blanket obec polygon.
    Obec category alone (no buildings in district) must NOT raise SIGNAL."""

    def _patch_pe(self, c_pe, cat_rows, bld_rows):
        calls = {"i": 0}

        def fake(sql, *a, **k):
            calls["i"] += 1
            return cat_rows if calls["i"] == 1 else bld_rows

        return mock.patch.object(c_pe, "query_sql", side_effect=fake)

    def test_obec_category_without_buildings_no_signal(self):
        import engine.c_pe as c_pe
        cat = [{"category": "large", "obec_name": "Prešov"}]
        bld = [{"n": 0, "n_demo": 0}]
        with self._patch_pe(c_pe, cat, bld):
            v = c_pe.check_pe(_D, _D["municipality_id"])
        assert v.value == V.NO_SIGNAL, "blanket obec category must not be a per-district SIGNAL"

    def test_locality_buildings_signal(self):
        import engine.c_pe as c_pe
        cat = [{"category": "large", "obec_name": "Prešov"}]
        bld = [{"n": 12, "n_demo": 12}]
        with self._patch_pe(c_pe, cat, bld):
            v = c_pe.check_pe(_D, _D["municipality_id"])
        assert v.value == V.SIGNAL
        assert v.is_mock is True  # demo buildings

    def test_no_atlas_context_not_evaluated(self):
        import engine.c_pe as c_pe
        with self._patch_pe(c_pe, [], [{"n": 0, "n_demo": 0}]):
            v = c_pe.check_pe(_D, _D["municipality_id"])
        assert v.value == V.NOT_EVALUATED
