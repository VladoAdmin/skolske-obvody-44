"""
VLA-14 coverage-gap classifier — intent guards.

WHY these matter:
  * The vzn_gap category IS the structural Š1-family finding — its evidence
    must cite § 44 so the popup/register wording stays legally anchored.
  * The refresh must never delete is_demo rows (demo/mock data invariant).
  * VLA-20 retired the data_gap ("nedostatočné dáta") category entirely: the
    classifier must not emit it, so the state can never reappear in the GUI.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import coverage_gaps as cg

_MUN = "00000000-0000-0000-0000-00000000mun1"


# ------------------------------------------------------------ evidence intent
def test_vzn_gap_reason_cites_structural_s1():
    """The VZN gap is a legitimate structural finding — its evidence must stay
    anchored to Š1 / § 44 ods. 1 (every address belongs to exactly one
    district), not become generic prose."""
    assert "§ 44 ods. 1" in cg.REASON_VZN_GAP_SK
    assert "Š1" in cg.REASON_VZN_GAP_SK
    assert "žiadne VZN" in cg.REASON_VZN_GAP_SK


def test_reason_template_placeholder_arity_matches_sql_format_call():
    """The template is consumed by SQL format() with a fixed argument list
    (street + address count). A placeholder-count drift would make every
    engine run fail at INSERT time."""
    assert cg.REASON_VZN_GAP_SK.count("%s") == 2


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


def test_classifier_emits_only_vzn_gap():
    """VLA-20: the data_gap ("nedostatočné dáta") state was removed from the
    product. The classifier must run exactly one category insert, scoped to
    vzn_gap and sourced from the register-vs-VZN diff — if data_gap ever
    reappears here, the removed state would leak back into the GUI."""
    executed, stats = _run_classifier_capturing_sql()
    assert stats == {"vzn_gap": 0}
    assert len(executed) == 2  # DELETE + single vzn_gap INSERT

    vzn_sql = executed[1]
    assert "'vzn_gap'" in vzn_sql
    assert "data_gap" not in vzn_sql
    assert "register_adries_clean" in vzn_sql
    assert cg.REASON_VZN_GAP_SK.split("%s")[0] in vzn_sql
