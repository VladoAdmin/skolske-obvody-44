"""
Š3 — Jedna škola na obvod (One public school per district).

METHODOLOGY §Š3:
  PASS = exactly 1 public school of matching type within district.geom.
  FAIL = 0 or >1 public schools within geom.
  INCOMPLETE = school_id FK missing on district.

Only public schools (is_public=TRUE) of matching school_type are counted.
Private/church schools (§44 covers only public MŠ/ZŠ) are excluded.

Note: the district.school_id FK is the VZN-assigned school; we ALSO spatially
count public schools whose Point is within the district boundary. Discrepancy
between FK assignment and spatial count is flagged in evidence.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

_METHODOLOGY = {
    "rule": "Š3-one-school",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Count public schools (is_public=TRUE) of matching school_type whose "
        "ST_Within(school.geom, district.geom). PASS = exactly 1."
    ),
    "law_ref": "§44 ods. 1",
    "never_claims": (
        "status of private/church schools; "
        "only public MŠ/ZŠ enter the count"
    ),
}


def check_s3(district: dict) -> Verdict:
    district_id = district["id"]
    school_id = district.get("school_id")
    school_type = district.get("school_type", "ZS")

    # If FK missing → INCOMPLETE
    if not school_id:
        return Verdict(
            district_id=district_id,
            condition_code="S3",
            value=V.INCOMPLETE,
            confidence=0.0,
            data_completeness=0.3,
            provenance={
                "source": "districts.school_id FK",
                "reason": "school_id IS NULL — škola k obvodu nepriradená",
            },
            methodology=_METHODOLOGY,
            evidence_text="NEÚPLNÉ: k tomuto obvodu nie je priradená škola (school_id = NULL).",
        )

    # Spatial count: how many public schools of same type are inside this district
    count_rows = query_sql(f"""
        SELECT COUNT(*) as n
        FROM skolske_obvody.schools s
        JOIN skolske_obvody.districts d ON d.id = '{district_id}'
        WHERE s.is_public = TRUE
          AND s.type = '{school_type}'
          AND public.ST_Within(s.geom, d.geom)
    """)
    spatial_count = int(count_rows[0]["n"]) if count_rows else 0

    # Also verify the FK-assigned school is the one inside
    fk_inside_rows = query_sql(f"""
        SELECT public.ST_Within(s.geom, d.geom) as inside
        FROM skolske_obvody.schools s
        JOIN skolske_obvody.districts d ON d.id = '{district_id}'
        WHERE s.id = '{school_id}'
    """)
    fk_inside = bool(fk_inside_rows[0]["inside"]) if fk_inside_rows else False

    provenance = {
        "source": "schools (q9) + district geom (q6)",
        "school_type": school_type,
        "fk_school_id": school_id,
        "fk_school_inside_geom": fk_inside,
        "spatial_count_public_schools": spatial_count,
        "note": "Only public schools (is_public=TRUE) counted per §44.",
    }

    if spatial_count == 1:
        value = V.PASS
        evidence = (
            f"PASS: 1 verejná škola typu {school_type} v obvode (priestorový test). "
            f"FK-priradená škola je v geometrii: {fk_inside}."
        )
        confidence = 0.75 if fk_inside else 0.55  # lower if FK doesn't match spatial
    elif spatial_count == 0:
        value = V.FAIL
        evidence = (
            f"FAIL: 0 verejných škôl typu {school_type} priestorovo v obvode. "
            f"FK-priradená škola ({school_id}) je v geometrii: {fk_inside}. "
            "Geometria obvodu môže nepresne pokrývať polohu školy (q6)."
        )
        confidence = 0.6
    else:  # > 1
        value = V.FAIL
        evidence = (
            f"FAIL: {spatial_count} verejných škôl typu {school_type} v obvode "
            "(očakáva sa práve 1)."
        )
        confidence = 0.7

    return Verdict(
        district_id=district_id,
        condition_code="S3",
        value=value,
        confidence=confidence,
        data_completeness=0.8,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
    )
