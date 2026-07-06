"""
VLA-14 coverage-gap classifier — intent guards.

WHY these matter:
  * The data_gap category exists precisely so an undecidable street is NEVER
    presented as a § 44 violation (same discipline as mock-never-RED). The
    evidence template must always negate a violation and say "neurčené".
  * The vzn_gap category IS the structural Š1-family finding — its evidence
    must cite § 44 so the popup/register wording stays legally anchored.
  * The refresh must never delete is_demo rows (demo/mock data invariant) and
    each category insert must be scoped to its own category literal.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import coverage_gaps as cg

_MUN = "00000000-0000-0000-0000-00000000mun1"


# ------------------------------------------------------------ evidence intent
def test_data_gap_reason_never_reads_as_violation():
    """A data gap must explicitly negate a violation and declare itself
    undecided — if this wording ever changes to an accusation, the map would
    render a non-finding as a § 44 problem."""
    assert "Neurčené" in cg.REASON_DATA_GAP_SK
    assert "dátová medzera" in cg.REASON_DATA_GAP_SK
    assert "Nejde o zistené porušenie § 44" in cg.REASON_DATA_GAP_SK


def test_vzn_gap_reason_cites_structural_s1():
    """The VZN gap is a legitimate structural finding — its evidence must stay
    anchored to Š1 / § 44 ods. 1 (every address belongs to exactly one
    district), not become generic prose."""
    assert "§ 44 ods. 1" in cg.REASON_VZN_GAP_SK
    assert "Š1" in cg.REASON_VZN_GAP_SK
    assert "žiadne VZN" in cg.REASON_VZN_GAP_SK


def test_reason_templates_placeholder_arity_matches_sql_format_calls():
    """The templates are consumed by SQL format() with a fixed argument list
    (vzn_gap: street + address count; data_gap: street). A placeholder-count
    drift would make every engine run fail at INSERT time."""
    assert cg.REASON_VZN_GAP_SK.count("%s") == 2
    assert cg.REASON_DATA_GAP_SK.count("%s") == 1


# ------------------------------------------------------------- SQL invariants
def _run_classifier_capturing_sql():
    executed = []

    def fake_exec_sql(sql: str):
        executed.append(sql)
        return {"ok": True}

    def fake_query_sql(sql: str):
        return []  # summary query — no rows needed

    with mock.patch.object(cg, "exec_sql", side_effect=fake_exec_sql), \
         mock.patch.object(cg, "query_sql", side_effect=fake_query_sql):
        stats = cg.classify_coverage_gaps(_MUN)
    return executed, stats


def test_refresh_never_deletes_demo_rows():
    """is_demo rows are seeded/owned separately (mock data invariant) — the
    engine's full refresh may only wipe its own real-data derivations."""
    executed, _ = _run_classifier_capturing_sql()
    delete = executed[0]
    assert delete.strip().startswith("DELETE FROM skolske_obvody.street_coverage_gaps")
    assert "is_demo = FALSE" in delete
    assert _MUN in delete


def test_each_insert_scoped_to_its_own_category():
    """vzn_gap rows must come from the register-vs-VZN diff; data_gap rows from
    the OSM-vs-(VZN+register) diff. Crossing the streams would classify an
    undecidable street as a violation."""
    executed, stats = _run_classifier_capturing_sql()
    assert stats == {"vzn_gap": 0, "data_gap": 0}
    vzn_sql, data_sql = executed[1], executed[2]

    assert "'vzn_gap'" in vzn_sql and "'data_gap'" not in vzn_sql
    assert "register_adries_clean" in vzn_sql
    assert cg.REASON_VZN_GAP_SK.split("%s")[0] in vzn_sql

    assert "'data_gap'" in data_sql and "'vzn_gap'" not in data_sql
    # data_gap requires BOTH negative joins: not in VZN and not in register
    assert data_sql.count("NOT EXISTS") == 2
    assert cg.REASON_DATA_GAP_SK.split("%s")[0] in data_sql
