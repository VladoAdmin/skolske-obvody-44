"""
Demo-mode input loader.

When demo mode is enabled for the municipality AND a district has a row in
skolske_obvody.district_demo_inputs, the checkers read that row and emit a
DECISIVE, high-confidence verdict (confidence/completeness >= 0.90), flagged
is_mock=TRUE so the UI badges it DEMO. With no demo row, checkers keep their
honest real-data behaviour (INSUFFICIENT_DATA / INCOMPLETE when data is missing).

The loader is cached per process run so each checker call is cheap.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional, TypedDict

from ingest.supabase_client import query_sql

# High confidence/completeness assigned to any verdict derived from a complete
# demo input row. The demo represents "complete, credible data".
DEMO_CONFIDENCE = 0.95
DEMO_COMPLETENESS = 0.95


class DistrictDemoInput(TypedDict, total=False):
    """Typed shape of a skolske_obvody.district_demo_inputs row.

    This is the engine-facing contract for per-district demo input: every
    field here is explicit, provenance-tagged demo data (never a value
    silently inferred from real tables). Checkers only see these fields when
    `demo_mode_enabled()` is True AND a row exists for the district — see
    `get_demo_input()`. With no row, checkers keep their honest real-data path.
    """

    district_id: str
    s1_total_addresses: Optional[int]
    s1_uncovered: Optional[int]
    s1_wrong_district: Optional[int]
    s2_overlap: Optional[bool]
    s3_school_count: Optional[int]
    pa_max_distance_m: Optional[float]
    pb_minutes: Optional[int]
    pb_distance_m: Optional[float]
    pc_transfers: Optional[int]
    pc_total_minutes: Optional[int]
    pd_barrier: Optional[bool]
    pd_barrier_kind: Optional[str]
    pe_mrk_signal: Optional[bool]
    pf_capacity: Optional[int]
    pf_enrolment: Optional[int]
    jazyk_language: Optional[str]
    note: Optional[str]


# Maps each of the six Step-2 demo scenario families (see
# docs/demo-analysis-layer-article-2026-06-30.md) to the condition code that
# consumes it and the field(s)/table that carry the demo input. This is the
# single source of truth proving every scenario is representable as engine
# input — tests assert against it, and Sprint 2/3 GUI filters can read it
# instead of re-deriving the mapping. It does not drive any verdict itself.
SCENARIO_FIELDS: dict[str, dict] = {
    "segregation_mrk": {
        "condition": "Pe",
        "source": "district_demo_inputs",
        "fields": ["pe_mrk_signal"],
    },
    "capacity_pressure": {
        "condition": "Pf",
        "source": "district_demo_inputs",
        "fields": ["pf_capacity", "pf_enrolment"],
    },
    "long_distance": {
        "condition": "Pa/Pb",
        "source": "district_demo_inputs",
        "fields": ["pa_max_distance_m", "pb_minutes", "pb_distance_m"],
    },
    "difficult_route": {
        "condition": "Pc/Pd",
        "source": "district_demo_inputs",
        "fields": ["pc_transfers", "pc_total_minutes", "pd_barrier", "pd_barrier_kind"],
    },
    "language_minority": {
        "condition": "JAZYK",
        "source": "district_demo_inputs",
        "fields": ["jazyk_language"],
    },
    # NOT sourced from district_demo_inputs: the address-overlap scenario is
    # address-level, not per-district, so it lives as explicit is_demo=TRUE
    # rows in house_geocodes. engine/c_s2.py runs its normal real-data query
    # over that data — the engine computes the FAIL, nothing is hand-written.
    "address_overlap": {
        "condition": "S2",
        "source": "house_geocodes(is_demo=TRUE)",
        "fields": ["street", "house_number"],
    },
}


# ONE-SHOT ASSUMPTION: these caches are process-lifetime (maxsize=1, never
# time-expired). That is safe ONLY because engine/runner.py is a one-shot CLI
# process (`python3 -m engine.runner`) that calls refresh_demo_mode() exactly
# once, at the very start of run(), before any checker reads the flag. If the
# engine is ever run as a long-lived process (server/worker) that must observe
# a demo_mode_flag toggle mid-run, these caches would silently serve a stale
# value — refresh_demo_mode() must be called again before each unit of work.
@lru_cache(maxsize=1)
def _demo_mode_enabled() -> bool:
    try:
        rows = query_sql(
            "SELECT bool_or(enabled) AS on FROM skolske_obvody.demo_mode_flag"
        )
    except Exception:
        return False
    return bool(rows and rows[0].get("on"))


def demo_mode_enabled() -> bool:
    """Public read of the demo-mode flag, for checkers that gate a real-data
    query (rather than swapping in a district_demo_inputs row) — e.g. c_s2
    including/excluding is_demo=TRUE house_geocodes rows."""
    return _demo_mode_enabled()


@lru_cache(maxsize=1)
def _all_demo_inputs() -> dict:
    """Load every district_demo_inputs row keyed by district_id (one DB hit)."""
    if not _demo_mode_enabled():
        return {}
    try:
        rows = query_sql(
            "SELECT * FROM skolske_obvody.district_demo_inputs"
        )
    except Exception:
        return {}
    return {str(r["district_id"]): r for r in rows}


def get_demo_input(district_id: str) -> Optional[DistrictDemoInput]:
    """Return the demo input row for a district, or None when not in demo mode."""
    return _all_demo_inputs().get(str(district_id))


def refresh_demo_mode() -> None:
    """Clear the demo-mode caches so the next read re-hits the DB.

    Must be called at the start of every engine run (see engine/runner.py
    run()) so a demo_mode_flag toggle made between runs is picked up. Within
    a single one-shot run this is called exactly once — see the one-shot
    assumption documented above _demo_mode_enabled().
    """
    _demo_mode_enabled.cache_clear()
    _all_demo_inputs.cache_clear()
