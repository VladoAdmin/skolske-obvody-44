"""
P-e — Sociálny kontext (Atlas MRK) — segregation/inclusion signal (analytical only).

METHODOLOGY §P-e (labels.ts canonical = "Sociálny kontext (Atlas MRK)"):
  Analytical signal, NEVER a legal verdict (Pe ∈ SIGNAL_CONDITIONS).

  Data reality in DB:
    - mrk_atlas = obec-level boundaries from "Atlas rómskych komunít 2019" tagged
      with a category (none/low/medium/large). For Prešov the whole obec is tagged
      'large'. This is municipality-level context — it does NOT locate a community
      within a particular district, so it cannot drive a per-district area share.
    - mrk_buildings = locality-level building points. These DO locate a community.

  Per-district signal logic:
    SIGNAL        = >= MRK_BUILDING_SIGNAL_MIN marginalized-community buildings fall
                    inside the district (real locality concentration), OR a DEMO
                    inclusion case is seeded for the district.
    NO_SIGNAL     = the obec has Atlas context but no locality buildings in this
                    district.
    NOT_EVALUATED = no Atlas context at all for this obec.

  DEMO inclusion case (Part B): a district may carry a seeded marginalized share
  (demographics_children provenance / mrk_buildings is_demo) to make an explicit
  "inclusion fails" example; such verdicts are flagged is_mock=TRUE.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

# Minimum locality buildings inside a district to raise a real segregation signal.
MRK_BUILDING_SIGNAL_MIN = 5

_METHODOLOGY = {
    "rule": "Pe-mrk-locality-buildings",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Sociálny kontext z Atlasu rómskych komunít 2019. Obecná kategória "
        "(mrk_atlas) je kontext na úrovni obce; konkrétnu lokalitu v obvode určujú "
        "len budovy MRK (mrk_buildings). Signál = koncentrácia budov MRK v obvode."
    ),
    "data_source": "Atlas rómskych komunít 2019: mrk_atlas (kategória obce) + mrk_buildings (lokalita)",
    "data_age": "Atlas 2019 — 6-ročné dáta; výsledok je analytický signál, nie verdikt",
    "building_signal_min": MRK_BUILDING_SIGNAL_MIN,
    "law_ref": "§44 ods. 8 písm. e)",
    "never_claims": (
        "segregácia/inklúzia ako zákonný verdikt; obecná kategória != per-obvod podiel"
    ),
    "panel": "analytické signály — NIKDY v zákonnom semafore",
}


def check_pe(district: dict, municipality_id: str) -> Verdict:
    district_id = district["id"]

    # Obec-level Atlas category (context only).
    cat_rows = query_sql(f"""
        SELECT a.category, a.obec_name
        FROM skolske_obvody.mrk_atlas a
        JOIN skolske_obvody.municipalities mun ON mun.id = '{municipality_id}'
        WHERE public.ST_Contains(a.geom, public.ST_Centroid(mun.geom))
        ORDER BY a.category DESC
        LIMIT 1
    """)
    obec_category = cat_rows[0]["category"] if cat_rows else None
    obec_name = cat_rows[0]["obec_name"] if cat_rows else None

    # Locality-level: MRK buildings inside this district (real + demo).
    bld_rows = query_sql(f"""
        SELECT
            COUNT(*) AS n,
            COUNT(*) FILTER (WHERE COALESCE(b.is_demo, FALSE)) AS n_demo
        FROM skolske_obvody.mrk_buildings b
        JOIN skolske_obvody.districts d ON d.id = '{district_id}'
        WHERE public.ST_Within(b.geom, d.geom)
    """)
    n_buildings = int(bld_rows[0]["n"]) if bld_rows else 0
    n_demo = int(bld_rows[0]["n_demo"]) if bld_rows else 0
    is_demo = n_demo > 0

    provenance = {
        "source": "Atlas rómskych komunít 2019 (mrk_atlas + mrk_buildings)",
        "data_year": 2019,
        "obec_atlas_category": obec_category,
        "obec_name": obec_name,
        "mrk_building_count_in_district": n_buildings,
        "mrk_building_demo_count": n_demo,
        "building_signal_min": MRK_BUILDING_SIGNAL_MIN,
        "caveat": "Atlas 2019; obecná kategória je kontext, nie per-obvod podiel",
    }

    if obec_category is None and n_buildings == 0:
        return Verdict(
            district_id=district_id,
            condition_code="Pe",
            value=V.NOT_EVALUATED,
            confidence=0.0,
            data_completeness=0.0,
            provenance=provenance,
            methodology=_METHODOLOGY,
            evidence_text=(
                "NEVYHODNOTENÉ: pre obec nie je v Atlase MRK 2019 žiadny kontext "
                "ani lokality v obvode. Analytický signál — nevstupuje do zákonného semaforu."
            ),
        )

    if n_buildings >= MRK_BUILDING_SIGNAL_MIN:
        value = V.SIGNAL
        evidence = (
            f"SIGNÁL: v obvode je {n_buildings} budov(y) marginalizovanej komunity "
            f"(Atlas MRK 2019, kategória obce: {obec_category or 'neznáma'}). "
            "Možný kontext segregácie/inklúzie — analytický signál, nie zákonný verdikt."
            + (" [DEMO inklúzia]" if is_demo else "")
        )
        confidence = 0.5
    else:
        value = V.NO_SIGNAL
        evidence = (
            f"BEZ SIGNÁLU na úrovni lokality: obec Prešov má v Atlase MRK 2019 kategóriu "
            f"„{obec_category or 'neznáma'}“ (kontext obce), ale v tomto obvode nie sú "
            f"lokality MRK ({n_buildings} budov). Obecná kategória nie je per-obvod podiel. "
            "Analytický signál — nevstupuje do zákonného semaforu."
        )
        confidence = 0.3

    return Verdict(
        district_id=district_id,
        condition_code="Pe",
        value=value,
        confidence=confidence,
        data_completeness=0.4,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
        is_proxy=True,
        is_mock=is_demo,
    )
