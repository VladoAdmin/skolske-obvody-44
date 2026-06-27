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
from typing import Optional

from ingest.supabase_client import query_sql

# High confidence/completeness assigned to any verdict derived from a complete
# demo input row. The demo represents "complete, credible data".
DEMO_CONFIDENCE = 0.95
DEMO_COMPLETENESS = 0.95


@lru_cache(maxsize=1)
def _demo_mode_enabled() -> bool:
    try:
        rows = query_sql(
            "SELECT bool_or(enabled) AS on FROM skolske_obvody.demo_mode_flag"
        )
    except Exception:
        return False
    return bool(rows and rows[0].get("on"))


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


def get_demo_input(district_id: str) -> Optional[dict]:
    """Return the demo input row for a district, or None when not in demo mode."""
    return _all_demo_inputs().get(str(district_id))


def reset_cache() -> None:
    """Clear caches (used by tests / a fresh engine run)."""
    _demo_mode_enabled.cache_clear()
    _all_demo_inputs.cache_clear()
