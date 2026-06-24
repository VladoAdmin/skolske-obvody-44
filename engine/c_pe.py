"""
P-e — Zákaz segregácie (Segregation signal — analytical only, never legal verdict).

METHODOLOGY §P-e:
  Compute MRK area share per district.
  SIGNAL   = MRK area > 10% of district area (PE_MRK_AREA_THRESHOLD).
  NO_SIGNAL = otherwise.
  NOT_EVALUATED = no MRK Atlas data for this municipality.

  Source: Atlas MRK 2019 (q7) + mrk_buildings.
  Deterministic only. No LLM in this sprint.
  Always shown in "analytické signály" sub-panel, never in legal semafor.
  Methodology JSONB notes data age (Atlas 2019).
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION, PE_MRK_AREA_THRESHOLD
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

_METHODOLOGY = {
    "rule": "Pe-segregation-mrk-area",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Podiel plochy MRK polygónov (Atlas MRK 2019) v obvode voči celkovej ploche obvodu. "
        "Prah: > 10% = SIGNÁL."
    ),
    "data_source": "Atlas MRK 2019 (q7) + mrk_buildings (q7)",
    "data_age": "Atlas 2019 — 6-ročné dáta; výsledok je analytický signál, nie verdikt",
    "threshold_pct": PE_MRK_AREA_THRESHOLD * 100,
    "law_ref": "§44 ods. 8 písm. e)",
    "never_claims": "segregácia/nesegregácia ako zákonný verdikt; Atlas 2019; analytický signál",
    "panel": "analytické signály — NIKDY v zákonnom semafore",
}


def check_pe(district: dict, municipality_id: str) -> Verdict:
    district_id = district["id"]

    # Check if Atlas MRK has any data for this municipality's region
    # mrk_atlas is linked by obec_id (municipality id) or spatial intersection
    mrk_rows = query_sql(f"""
        SELECT
            SUM(public.ST_Area(public.ST_Transform(
                public.ST_Intersection(a.geom, d.geom),
                32634
            ))) AS mrk_area_m2,
            public.ST_Area(public.ST_Transform(d.geom, 32634)) AS district_area_m2
        FROM skolske_obvody.districts d
        LEFT JOIN skolske_obvody.mrk_atlas a
          ON public.ST_Intersects(a.geom, d.geom)
        WHERE d.id = '{district_id}'
        GROUP BY d.geom
    """)

    # Also check mrk_buildings
    bld_rows = query_sql(f"""
        SELECT COUNT(*) as n
        FROM skolske_obvody.mrk_buildings b
        JOIN skolske_obvody.districts d ON d.id = '{district_id}'
        WHERE public.ST_Within(b.geom, d.geom)
    """)
    mrk_building_count = int(bld_rows[0]["n"]) if bld_rows else 0

    if not mrk_rows or mrk_rows[0]["district_area_m2"] is None:
        return Verdict(
            district_id=district_id,
            condition_code="Pe",
            value=V.NOT_EVALUATED,
            confidence=0.0,
            data_completeness=0.0,
            provenance={"reason": "district geom unavailable for MRK intersection"},
            methodology=_METHODOLOGY,
            evidence_text="NEVYHODNOTENÉ: geometria obvodu nedostupná pre MRK analýzu.",
        )

    mrk_area = float(mrk_rows[0]["mrk_area_m2"] or 0)
    district_area = float(mrk_rows[0]["district_area_m2"] or 1)
    mrk_share = mrk_area / district_area if district_area > 0 else 0.0

    has_atlas_overlap = mrk_area > 0

    if not has_atlas_overlap and mrk_building_count == 0:
        value = V.NOT_EVALUATED
        evidence = (
            "NEVYHODNOTENÉ: žiadne MRK Atlas polygóny ani MRK budovy v tomto obvode. "
            "Analytický signál — nevstupuje do zákonného semaforu."
        )
    elif mrk_share > PE_MRK_AREA_THRESHOLD:
        value = V.SIGNAL
        evidence = (
            f"SIGNÁL: MRK plocha = {round(mrk_share * 100, 1)}% plochy obvodu "
            f"(prah: {PE_MRK_AREA_THRESHOLD * 100}%). "
            f"MRK budovy v obvode: {mrk_building_count}. "
            "Dáta: Atlas MRK 2019 — analytický signál, nie zákonný verdikt."
        )
    else:
        value = V.NO_SIGNAL
        evidence = (
            f"BEZ SIGNÁLU: MRK plocha = {round(mrk_share * 100, 1)}% plochy obvodu "
            f"(prah: {PE_MRK_AREA_THRESHOLD * 100}%). "
            f"MRK budovy: {mrk_building_count}. "
            "Atlas MRK 2019 — analytický signál."
        )

    provenance = {
        "source": "Atlas MRK 2019 (mrk_atlas, q7) + mrk_buildings (q7)",
        "data_year": 2019,
        "mrk_area_m2": round(mrk_area, 1),
        "district_area_m2": round(district_area, 1),
        "mrk_share_pct": round(mrk_share * 100, 2),
        "mrk_building_count": mrk_building_count,
        "threshold_pct": PE_MRK_AREA_THRESHOLD * 100,
        "caveat": "Atlas 2019 — 6 rokov starý; signál len indikatívny",
    }

    return Verdict(
        district_id=district_id,
        condition_code="Pe",
        value=value,
        confidence=0.5 if has_atlas_overlap else 0.0,
        data_completeness=0.5 if has_atlas_overlap else 0.0,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
        is_proxy=True,
    )
