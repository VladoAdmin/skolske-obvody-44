"""
7 synthetic fixtures for engine composition tests (PLAN §3 step 5).

Each fixture is a dict mapping condition_code → Verdict.
Fixtures test the composition rule: composition.py compose_color().

Fixtures:
  1. green_town           — all PASS → GREEN
  2. coverage_gap_town    — Š1 FAIL → RED
  3. overlap_town         — Š2 FAIL → RED
  4. missing_address_town — Š1 INCOMPLETE → ORANGE
  5. missing_school_town  — Š3 INCOMPLETE → ORANGE
  6. proxy_capacity       — Pa INSUFFICIENT_DATA → ORANGE (never RED)
  7. no_transit           — Pc ILUSTR_NO_DATA → ORANGE from other indicator, Pc never causes RED

All use fake district_id 'test-district-xxx'.
"""

from __future__ import annotations

from engine.constants import V
from engine.verdict import Verdict

_D = "00000000-0000-0000-0000-000000000001"  # fake district id


def _v(code: str, value: str, **kwargs) -> Verdict:
    """Helper to create a Verdict with minimal boilerplate."""
    return Verdict(
        district_id=_D,
        condition_code=code,
        value=value,
        confidence=0.8,
        data_completeness=0.8,
        provenance={"source": "test_fixture"},
        methodology={"rule": f"test-{code}", "version": "0.1"},
        evidence_text=f"Fixture {code}={value}",
        **kwargs,
    )


def _base_verdicts() -> dict:
    """All-PASS base verdicts."""
    return {
        "S1": _v("S1", V.PASS),
        "S2": _v("S2", V.PASS),
        "S3": _v("S3", V.PASS),
        "Pa": _v("Pa", V.PASS),
        "Pb": _v("Pb", V.PASS),
        "Pc": _v("Pc", V.PASS, is_illustrative=False),
        "Pd": _v("Pd", V.PASS),
        "Pe": _v("Pe", V.NO_SIGNAL),
        "Pf": _v("Pf", V.NOT_EVALUATED, is_mock=True),
    }


# --- Fixture 1: green_town ---
# All legal conditions PASS, no risky indicators → GREEN
GREEN_TOWN = _base_verdicts()

# --- Fixture 2: coverage_gap_town ---
# Š1 = FAIL → RED (legal condition fails)
COVERAGE_GAP_TOWN = {**_base_verdicts(), "S1": _v("S1", V.FAIL)}

# --- Fixture 3: overlap_town ---
# Š2 = FAIL → RED (legal condition fails)
OVERLAP_TOWN = {**_base_verdicts(), "S2": _v("S2", V.FAIL)}

# --- Fixture 4: missing_address_town ---
# Š1 = INCOMPLETE (no address_points) → ORANGE
MISSING_ADDRESS_TOWN = {**_base_verdicts(), "S1": _v("S1", V.INCOMPLETE, is_proxy=True)}

# --- Fixture 5: missing_school_town ---
# Š3 = INCOMPLETE (school_id NULL) → ORANGE
MISSING_SCHOOL_TOWN = {**_base_verdicts(), "S3": _v("S3", V.INCOMPLETE)}

# --- Fixture 6: proxy_capacity ---
# Pa = INSUFFICIENT_DATA (EDUZBER GAP) → ORANGE, NEVER RED
# Key assertion: RED must not be raised from Pa alone
PROXY_CAPACITY = {
    **_base_verdicts(),
    "Pa": _v("Pa", V.INSUFFICIENT_DATA, is_proxy=True),
}

# --- Fixture 7: no_transit ---
# Pc = ILUSTR_NO_DATA (illustrative, no API key) → Pc never raises FAIL
# Pa = INSUFFICIENT_DATA for good measure → ORANGE from Pa (not from Pc)
NO_TRANSIT = {
    **_base_verdicts(),
    "Pa": _v("Pa", V.INSUFFICIENT_DATA, is_proxy=True),
    "Pc": _v("Pc", V.ILUSTR_NO_DATA, is_illustrative=True),
}

ALL_FIXTURES = {
    "green_town": GREEN_TOWN,
    "coverage_gap_town": COVERAGE_GAP_TOWN,
    "overlap_town": OVERLAP_TOWN,
    "missing_address_town": MISSING_ADDRESS_TOWN,
    "missing_school_town": MISSING_SCHOOL_TOWN,
    "proxy_capacity": PROXY_CAPACITY,
    "no_transit": NO_TRANSIT,
}
