"""
Engine composition tests — verifies the semafor composition rule over 7 fixtures.

Key invariants per PLAN §3 (hard merge gate):
  - RED only from Š FAIL (S1/S2/S3)
  - Pa/Pc/Pf/MOCK never cause RED
  - INCOMPLETE in S-conditions → ORANGE (not RED)
  - INSUFFICIENT_DATA in Pa/Pd → ORANGE (not RED)
  - ILUSTR_NO_DATA in Pc → never degrades legal status
  - Pe/Pf always in signal_status, never trigger color change

Run: cd projects/skolske-obvody-44 && python3 -m pytest tests/test_engine_compose.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from engine.compose import compose_color
from engine.constants import Color, V
from tests.fixtures.fixture_data import (
    GREEN_TOWN,
    COVERAGE_GAP_TOWN,
    OVERLAP_TOWN,
    MISSING_ADDRESS_TOWN,
    MISSING_SCHOOL_TOWN,
    PROXY_CAPACITY,
    NO_TRANSIT,
    ALL_FIXTURES,
)


class TestCompositionRules:
    """Verify composition output for all 7 fixtures."""

    def test_green_town_is_green(self):
        result = compose_color(GREEN_TOWN)
        assert result["color"] == Color.GREEN, (
            f"green_town must be GREEN, got {result['color']} — reason: {result['reason']}"
        )

    def test_coverage_gap_is_red(self):
        result = compose_color(COVERAGE_GAP_TOWN)
        assert result["color"] == Color.RED, (
            f"coverage_gap_town (S1=FAIL) must be RED, got {result['color']}"
        )

    def test_overlap_town_is_red(self):
        result = compose_color(OVERLAP_TOWN)
        assert result["color"] == Color.RED, (
            f"overlap_town (S2=FAIL) must be RED, got {result['color']}"
        )

    def test_missing_address_town_is_orange(self):
        result = compose_color(MISSING_ADDRESS_TOWN)
        assert result["color"] == Color.ORANGE, (
            f"missing_address_town (S1=INCOMPLETE) must be ORANGE, got {result['color']}"
        )

    def test_missing_school_town_is_orange(self):
        result = compose_color(MISSING_SCHOOL_TOWN)
        assert result["color"] == Color.ORANGE, (
            f"missing_school_town (S3=INCOMPLETE) must be ORANGE, got {result['color']}"
        )

    def test_proxy_capacity_is_orange_not_red(self):
        """Pa=INSUFFICIENT_DATA must push to ORANGE, never RED."""
        result = compose_color(PROXY_CAPACITY)
        assert result["color"] == Color.ORANGE, (
            f"proxy_capacity (Pa=INSUFFICIENT_DATA) must be ORANGE, got {result['color']}"
        )
        assert result["color"] != Color.RED, (
            "Pa=INSUFFICIENT_DATA must NEVER cause RED (gatekeeping rule)"
        )

    def test_no_transit_pc_never_raises_fail(self):
        """Pc=ILUSTR_NO_DATA (is_illustrative=True) must not degrade legal status.
        Color is ORANGE due to Pa=INSUFFICIENT_DATA, but that comes from Pa not Pc."""
        result = compose_color(NO_TRANSIT)
        # Pa=INSUFFICIENT_DATA → ORANGE
        assert result["color"] == Color.ORANGE, (
            f"no_transit must be ORANGE (from Pa), got {result['color']}"
        )
        assert result["color"] != Color.RED, (
            "ILUSTR_NO_DATA in Pc must NEVER cause RED"
        )


class TestGatekeepingInvariants:
    """Hard merge gate checklist — composition invariants."""

    def test_red_only_from_s_fail(self):
        """RED must only occur when a legal condition (S1/S2/S3) = FAIL."""
        for name, fixture in ALL_FIXTURES.items():
            result = compose_color(fixture)
            if result["color"] == Color.RED:
                legal = result["legal_status"]
                assert any(v == V.FAIL for v in legal.values()), (
                    f"Fixture '{name}': RED without S-FAIL — gatekeeping violated. "
                    f"legal_status={legal}"
                )

    def test_pa_insufficient_data_never_red(self):
        """Pa=INSUFFICIENT_DATA alone must not cause RED."""
        from tests.fixtures.fixture_data import _v, _base_verdicts
        verdicts = {**_base_verdicts(), "Pa": _v("Pa", V.INSUFFICIENT_DATA, is_proxy=True)}
        result = compose_color(verdicts)
        assert result["color"] != Color.RED, (
            "Pa=INSUFFICIENT_DATA alone must not cause RED"
        )

    def test_pc_ilustr_no_data_never_red(self):
        """Pc=ILUSTR_NO_DATA (is_illustrative) must not cause RED."""
        from tests.fixtures.fixture_data import _v, _base_verdicts
        verdicts = {
            **_base_verdicts(),
            "Pc": _v("Pc", V.ILUSTR_NO_DATA, is_illustrative=True),
        }
        result = compose_color(verdicts)
        assert result["color"] != Color.RED, (
            "Pc=ILUSTR_NO_DATA must not cause RED"
        )

    def test_pf_not_evaluated_never_degrades(self):
        """Pf=NOT_EVALUATED (is_mock) must not affect legal semafor."""
        from tests.fixtures.fixture_data import _v, _base_verdicts
        verdicts = {
            **_base_verdicts(),
            "Pf": _v("Pf", V.NOT_EVALUATED, is_mock=True),
        }
        result = compose_color(verdicts)
        # Should remain GREEN (all S pass, no risky indicators)
        assert result["color"] == Color.GREEN, (
            f"Pf=NOT_EVALUATED must not affect semafor, got {result['color']}"
        )

    def test_pe_signal_never_in_semafor_color(self):
        """Pe=SIGNAL must go only to signal_status, never degrade legal color."""
        from tests.fixtures.fixture_data import _v, _base_verdicts
        verdicts = {
            **_base_verdicts(),
            "Pe": _v("Pe", V.SIGNAL, is_proxy=True),
        }
        result = compose_color(verdicts)
        assert result["color"] == Color.GREEN, (
            f"Pe=SIGNAL must not degrade semafor, got {result['color']}"
        )
        assert "Pe" in result["signal_status"], (
            "Pe must appear in signal_status, not affect color"
        )

    def test_s1_s2_s3_pass_with_all_indicators_insufficient(self):
        """All S=PASS + all P indicators = INSUFFICIENT_DATA → ORANGE (not RED, not GREEN)."""
        from tests.fixtures.fixture_data import _v
        verdicts = {
            "S1": _v("S1", V.PASS),
            "S2": _v("S2", V.PASS),
            "S3": _v("S3", V.PASS),
            "Pa": _v("Pa", V.INSUFFICIENT_DATA, is_proxy=True),
            "Pb": _v("Pb", V.INSUFFICIENT_DATA),
            "Pc": _v("Pc", V.ILUSTR_NO_DATA, is_illustrative=True),
            "Pd": _v("Pd", V.INSUFFICIENT_DATA, is_proxy=True),
            "Pe": _v("Pe", V.NOT_EVALUATED),
            "Pf": _v("Pf", V.NOT_EVALUATED, is_mock=True),
        }
        result = compose_color(verdicts)
        assert result["color"] == Color.ORANGE, (
            f"All S PASS + indicators INSUFFICIENT_DATA should be ORANGE, got {result['color']}"
        )


class TestVerdictSchema:
    """Verify Verdict objects have all required 5-tuple fields."""

    def test_verdict_has_five_tuple_fields(self):
        from engine.verdict import Verdict
        v = Verdict(
            district_id="test-id",
            condition_code="S1",
            value=V.PASS,
            confidence=0.8,
            data_completeness=0.7,
            provenance={"source": "test"},
            methodology={"rule": "test", "version": "0.1"},
        )
        assert v.value is not None
        assert 0 <= v.confidence <= 1
        assert 0 <= v.data_completeness <= 1
        assert isinstance(v.provenance, dict)
        assert isinstance(v.methodology, dict)

    def test_verdict_to_db_record(self):
        import json
        from engine.verdict import Verdict
        v = Verdict(
            district_id="test-id",
            condition_code="S1",
            value=V.PASS,
            confidence=0.8,
            data_completeness=0.7,
            provenance={"source": "test"},
            methodology={"rule": "test", "version": "0.1"},
        )
        rec = v.to_db_record()
        assert "id" in rec
        assert "value" in rec
        assert "confidence" in rec
        assert "data_completeness" in rec
        assert "provenance" in rec
        # provenance is JSON string in db record
        prov = json.loads(rec["provenance"])
        assert prov["source"] == "test"
