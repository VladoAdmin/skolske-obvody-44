"""
Regression: the Š3 SPATIAL path must exclude is_demo=TRUE schools.

WHY this matters (reviewer hardening):
  A DEMO-flagged second school (eduid DEMO-SMERALOVA-2) lives in
  skolske_obvody.schools so the MAP can render two pins for Šmeralova. The
  invariant is that demo/mock data lives ONLY in input tables and must NEVER
  change an engine verdict. check_s3()'s non-demo path runs two spatial SQL
  queries against schools (a COUNT and the FK ST_Within check). If those
  queries do NOT filter out is_demo rows, a future engine run — or ANY district
  that falls back to the spatial path — could COUNT the demo school and flip an
  S3 PASS→FAIL. These tests assert both spatial queries carry the
  `s.is_demo IS NOT TRUE` exclusion. Removing the filter from c_s3.py makes
  them FAIL.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.constants import V

# District WITHOUT a demo input row → check_s3 takes the SPATIAL (real-data) path.
_D_SPATIAL = {
    "id": "00000000-0000-0000-0000-0000000000ff",
    "school_id": "00000000-0000-0000-0000-0000000000aa",
    "school_type": "ZS",
    "geometry_confidence": "high",
}


def _run_spatial_capturing_sql():
    """Run check_s3 on the spatial path, returning the list of SQL strings issued."""
    import engine.c_s3 as c
    captured: list[str] = []

    def fake_query_sql(sql: str):
        captured.append(sql)
        # First call = COUNT(*), second = FK ST_Within.
        if "COUNT(*)" in sql:
            return [{"n": 1}]
        return [{"inside": True}]

    # No demo input → force the real spatial code path.
    with mock.patch.object(c, "get_demo_input", return_value=None), \
         mock.patch.object(c, "query_sql", side_effect=fake_query_sql):
        verdict = c.check_s3(_D_SPATIAL)
    return captured, verdict


def test_s3_spatial_count_excludes_demo_schools():
    """The COUNT(*) spatial query must exclude is_demo=TRUE so the demo school
    can never enter the engine count (would FAIL if the filter were removed)."""
    sqls, _ = _run_spatial_capturing_sql()
    count_sql = next(s for s in sqls if "COUNT(*)" in s)
    norm = " ".join(count_sql.split()).lower()
    assert "s.is_demo is not true" in norm, (
        "Š3 spatial COUNT query is missing the `s.is_demo IS NOT TRUE` exclusion — "
        "demo schools could be counted and flip an engine verdict."
    )


def test_s3_fk_inside_query_excludes_demo_schools():
    """The FK ST_Within spatial query must also exclude is_demo=TRUE."""
    sqls, _ = _run_spatial_capturing_sql()
    fk_sql = next(s for s in sqls if "ST_Within" in s and "COUNT(*)" not in s)
    norm = " ".join(fk_sql.split()).lower()
    assert "s.is_demo is not true" in norm, (
        "Š3 FK-inside query is missing the `s.is_demo IS NOT TRUE` exclusion."
    )


def test_smeralova_s3_fail_is_demo_input_driven_not_schools_table():
    """Šmeralova's S3 FAIL must come from the DEMO INPUT (s3_school_count=2),
    independent of the schools table — proving the demo school in `schools`
    is invisible to the engine verdict."""
    import engine.c_s3 as c
    with mock.patch.object(c, "get_demo_input", return_value={"s3_school_count": 2}), \
         mock.patch.object(c, "query_sql") as q:
        v = c.check_s3({"id": _D_SPATIAL["id"], "school_id": None, "school_type": "ZS"})
    assert v.value == V.FAIL
    assert v.is_mock is True
    assert v.provenance.get("public_school_count") == 2
    # The demo path must NOT touch the schools table at all.
    q.assert_not_called()
