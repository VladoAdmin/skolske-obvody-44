"""
Š2 — Neprekrývanie (Non-overlap): districts for the same school_type + teaching_language
must not overlap.

METHODOLOGY §Š2:
  PASS = 0 overlap pairs (within tolerance).
  FAIL = any overlap pair (with area > tolerance).
  INCOMPLETE = missing geometry or missing school_type/teaching_language attribute.

Per VZN reality: boundary streets shared between districts → boundary lines
are analytically ambiguous. We use a 1 m² tolerance to ignore pure boundary
artefacts (ST_Touches patterns).

Evidence: record overlap area and partner district for each FAIL.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

# 1 m² tolerance for boundary artefacts (CoordSys: EPSG:32634)
OVERLAP_TOLERANCE_M2 = 1.0

_METHODOLOGY = {
    "rule": "Š2-overlap",
    "version": METHODOLOGY_VERSION,
    "threshold_m2": OVERLAP_TOLERANCE_M2,
    "description": (
        "Spatial intersection test between district pairs with matching "
        "school_type AND teaching_language. Boundary artefacts < 1 m² ignored. "
        "VZN boundary streets are ambiguous by construction — overlap > tolerance "
        "logged as analytical finding but marked FAIL."
    ),
    "law_ref": "§44 ods. 1 a 7",
    "never_claims": "a small topological overlap = intentional administrative decision",
}


def check_s2(district: dict, all_districts: list[dict], municipality_id: str) -> Verdict:
    district_id = district["id"]
    school_type = district.get("school_type")
    teaching_language = district.get("teaching_language")

    if not school_type:
        return Verdict(
            district_id=district_id,
            condition_code="S2",
            value=V.INCOMPLETE,
            confidence=0.0,
            data_completeness=0.0,
            provenance={"source": "districts table", "reason": "missing school_type attribute"},
            methodology=_METHODOLOGY,
            evidence_text="NEÚPLNÉ: chýba atribút school_type — test neprebehol.",
        )

    lang_filter = (
        f"AND d2.teaching_language = '{teaching_language}'"
        if teaching_language
        else "AND d2.teaching_language IS NULL"
    )

    overlap_rows = query_sql(f"""
        SELECT
            d2.id AS partner_id,
            d2.name AS partner_name,
            public.ST_Area(public.ST_Transform(
                public.ST_Intersection(d1.geom, d2.geom),
                32634
            )) AS overlap_m2
        FROM skolske_obvody.districts d1
        JOIN skolske_obvody.districts d2
          ON d1.id != d2.id
         AND d2.school_type = '{school_type}'
         {lang_filter}
         AND d2.municipality_id = '{municipality_id}'
         AND public.ST_Intersects(d1.geom, d2.geom)
        WHERE d1.id = '{district_id}'
          AND public.ST_Area(public.ST_Transform(
                public.ST_Intersection(d1.geom, d2.geom),
                32634
              )) > {OVERLAP_TOLERANCE_M2}
    """)

    n_overlaps = len(overlap_rows)
    overlap_details = [
        {
            "partner_id": r["partner_id"],
            "partner_name": r["partner_name"],
            "overlap_m2": round(float(r["overlap_m2"]), 1),
        }
        for r in overlap_rows
    ]

    if n_overlaps == 0:
        return Verdict(
            district_id=district_id,
            condition_code="S2",
            value=V.PASS,
            confidence=0.7,
            data_completeness=0.7,
            provenance={
                "source": "district geometries (q6)",
                "school_type": school_type,
                "teaching_language": teaching_language,
                "overlap_pairs_checked": True,
                "tolerance_m2": OVERLAP_TOLERANCE_M2,
            },
            methodology=_METHODOLOGY,
            evidence_text=(
                f"0 prekryvov s inými obvodmi typu {school_type}/{teaching_language} "
                f"nad toleranciou {OVERLAP_TOLERANCE_M2} m²."
            ),
        )
    else:
        total_overlap = sum(d["overlap_m2"] for d in overlap_details)
        return Verdict(
            district_id=district_id,
            condition_code="S2",
            value=V.FAIL,
            confidence=0.7,
            data_completeness=0.7,
            provenance={
                "source": "district geometries (q6)",
                "school_type": school_type,
                "teaching_language": teaching_language,
                "overlap_pairs": overlap_details,
                "total_overlap_m2": round(total_overlap, 1),
                "tolerance_m2": OVERLAP_TOLERANCE_M2,
            },
            methodology=_METHODOLOGY,
            evidence_text=(
                f"FAIL: {n_overlaps} prekryv(ov) s obvodmi rovnakého typu {school_type}/{teaching_language}. "
                f"Celková plocha prekryvu: {round(total_overlap, 1)} m². "
                "Hraničné ulice medzi obvodmi môžu spôsobovať analytické dvojité pokrytie."
            ),
        )
