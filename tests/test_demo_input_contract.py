"""
Step 2 Sprint 1 — demo input contract tests.

WHY these matter:
  * The brief (docs/demo-analysis-layer-article-2026-06-30.md) requires six
    demo scenario families to be representable as explicit engine input:
    segregation/MRK, capacity pressure, long distance, difficult route,
    language minority (non-§44), and address overlap. SCENARIO_FIELDS is the
    single source of truth for that contract — a test locks its shape so a
    future edit can't silently drop a scenario family.
  * "Mock/demo must not leak into live/prod verdict mode" is a HARD invariant
    from the brief. It must be enforced by CONSTRUCTION (the demo-mode gate
    short-circuits before any district_demo_inputs row can be read), not just
    by convention — these tests prove the short-circuit, not just mock around it.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.compose import LEGAL_CONDITIONS, INDICATOR_CONDITIONS, SIGNAL_CONDITIONS


# --------------------------------------------------------------- scenario map
EXPECTED_SCENARIOS = {
    "segregation_mrk",
    "capacity_pressure",
    "long_distance",
    "difficult_route",
    "language_minority",
    "address_overlap",
}


def test_scenario_fields_covers_all_six_families():
    from engine.demo_inputs import SCENARIO_FIELDS
    assert set(SCENARIO_FIELDS.keys()) == EXPECTED_SCENARIOS, (
        "SCENARIO_FIELDS must cover exactly the six demo scenario families "
        "from the brief — no more, no fewer."
    )


def test_every_scenario_declares_a_condition_and_fields():
    from engine.demo_inputs import SCENARIO_FIELDS
    for name, spec in SCENARIO_FIELDS.items():
        assert spec.get("condition"), f"{name}: missing condition code"
        assert spec.get("fields"), f"{name}: missing input field(s)"
        assert spec.get("source"), f"{name}: missing source table/column"


def test_address_overlap_is_not_sourced_from_district_demo_inputs():
    """The overlap scenario is address-level (house_geocodes), not per-district
    — it must not be declared as living in district_demo_inputs, or a future
    reader could wrongly expect a district_demo_inputs column for it."""
    from engine.demo_inputs import SCENARIO_FIELDS
    assert SCENARIO_FIELDS["address_overlap"]["source"] != "district_demo_inputs"


# ------------------------------------------------------- demo/live gate (S1..)
def test_get_demo_input_returns_none_when_demo_mode_disabled():
    """Construction test: even if district_demo_inputs HAS a row for the
    district, get_demo_input() must return None while demo mode is off — the
    checkers must never see it."""
    import engine.demo_inputs as di
    di.refresh_demo_mode()
    calls = {"n": 0}

    def fake_query_sql(sql: str):
        calls["n"] += 1
        if "demo_mode_flag" in sql:
            return [{"on": False}]
        # Would return a full demo row IF ever reached — it must not be reached.
        return [{"district_id": "d1", "s1_total_addresses": 500}]

    with mock.patch.object(di, "query_sql", side_effect=fake_query_sql):
        result = di.get_demo_input("d1")

    assert result is None
    # _all_demo_inputs() must short-circuit on the disabled flag and never
    # issue the district_demo_inputs SELECT at all.
    assert calls["n"] == 1, (
        "get_demo_input queried district_demo_inputs while demo mode was "
        "disabled — mock data could leak into a live verdict."
    )
    di.refresh_demo_mode()


def test_get_demo_input_returns_row_when_demo_mode_enabled():
    import engine.demo_inputs as di
    di.refresh_demo_mode()

    def fake_query_sql(sql: str):
        if "demo_mode_flag" in sql:
            return [{"on": True}]
        return [{"district_id": "d1", "s1_total_addresses": 500, "s1_uncovered": 0, "s1_wrong_district": 0}]

    with mock.patch.object(di, "query_sql", side_effect=fake_query_sql):
        result = di.get_demo_input("d1")

    assert result is not None
    assert result["s1_total_addresses"] == 500
    di.refresh_demo_mode()


def test_demo_mode_enabled_public_wrapper_matches_internal_gate():
    """demo_mode_enabled() (used by c_s2's construction-level gate) must read
    the same flag as get_demo_input()'s internal gate — no second code path
    that could drift out of sync."""
    import engine.demo_inputs as di
    di.refresh_demo_mode()
    with mock.patch.object(di, "query_sql", return_value=[{"on": True}]):
        assert di.demo_mode_enabled() is True
    di.refresh_demo_mode()
    with mock.patch.object(di, "query_sql", return_value=[{"on": False}]):
        assert di.demo_mode_enabled() is False
    di.refresh_demo_mode()


# --------------------------------------------------------- JAZYK non-§44 lock
def test_jazyk_is_excluded_from_every_semafor_group():
    """Regression lock: JAZYK must never be added to LEGAL/INDICATOR/SIGNAL —
    it is a podnet mimo §44, not a §44 condition of any kind."""
    assert "JAZYK" not in LEGAL_CONDITIONS
    assert "JAZYK" not in INDICATOR_CONDITIONS
    assert "JAZYK" not in SIGNAL_CONDITIONS
