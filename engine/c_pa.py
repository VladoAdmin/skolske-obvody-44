"""
P-a — Kapacita budov (School capacity indicator).

METHODOLOGY §P-a:
  Without real EDUZBER capacity data, occupancy CANNOT be computed.
  Value = INSUFFICIENT_DATA, confidence = 0.0, completeness = 0.0.
  Provenance points to EDUZBER GAP.
  This verdict NEVER contributes to legal status (gatekeeping).

student_count from WFS is stored as an informational field only.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict

_METHODOLOGY = {
    "rule": "Pa-capacity-proxy",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Kapacita budov školy (EDUZBER) nie je v DB — GAP. "
        "Obsadenosť (žiaci/kapacita) sa nepočíta bez skutočnej kapacity. "
        "student_count z WFS je dostupný ako indikatívny údaj veľkosti školy."
    ),
    "gap": "EDUZBER capacity data not available",
    "law_ref": "§44 ods. 8 písm. a)",
    "never_claims": "škola je pre/podkapacitná bez skutočnej kapacity; žiadny právny záver",
    "gatekeeping": "INSUFFICIENT_DATA nikdy nezhoršuje zákonný semafor",
}


def check_pa(district: dict) -> Verdict:
    district_id = district["id"]
    school_name = district.get("school_name", "")
    student_count = district.get("student_count")

    provenance = {
        "source": "schools.capacity (EDUZBER) — GAP",
        "schools_wfs_student_count": student_count,
        "note": (
            "Kapacita z EDUZBER nie je dostupná. "
            "Počet žiakov z WFS je len indikátor veľkosti školy, nie obsadenosti. "
            "Reálna obsadenosť = žiaci / kapacita — nedostupné."
        ),
        "action_required": "Admin import kapacít z EDUZBER odblokuje tento indikátor.",
    }

    return Verdict(
        district_id=district_id,
        condition_code="Pa",
        value=V.INSUFFICIENT_DATA,
        confidence=0.0,
        data_completeness=0.0,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=(
            f"MÁLO DÁT: kapacita budov z EDUZBER nedostupná (GAP). "
            f"Škola: {school_name}. "
            f"Počet žiakov (WFS, indikatívny): {student_count if student_count else 'N/A'}. "
            "Indikátor nevstupuje do zákonného stavu."
        ),
        is_proxy=True,
    )
