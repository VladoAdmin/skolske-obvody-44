"""
P-d — Bariéry (cesty, koľaje) — physical barriers on the home→school route.

METHODOLOGY §P-d (labels.ts canonical = "Bariéry (cesty, koľaje)"):
  §44 ods. 8 písm. d) (metodika): the route from home to school should not cross
  a busy road without a crossing, nor a railway without an underpass.

  Computing this honestly requires a dataset of barrier features (railway lines,
  class-I/II roads WITH the locations of legal crossings) AND the pupil's pedestrian
  route. We have road_network (road centerlines, classes I/II/III) but:
    - no railway geometry,
    - no crossing/underpass locations,
    - no per-pupil route barrier intersection model.
  A barrier verdict computed without crossing data would be misleading (every
  district touches a class-I road), so we return INSUFFICIENT_DATA honestly.

  Value:
    INSUFFICIENT_DATA = no barrier dataset (railway + crossings) available.
  This is a risk INDICATOR (Pd ∈ INDICATOR_CONDITIONS); INSUFFICIENT_DATA can
  push to ORANGE but never RED.

  IMPORTANT: P-d is NOT about language. Minority-language teaching is handled as
  "podnet nad rámec § 44 (jazyk)" via a separate non-§44 finding — never under P-d.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

_METHODOLOGY = {
    "rule": "Pd-barriers-insufficient",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Fyzické bariéry na trase domov→škola (rušná cesta bez priechodu, "
        "železnica bez podchodu). Vyžaduje dataset bariér (železnice + polohy "
        "priechodov/podchodov) a pešiu trasu žiaka. Tieto dáta nie sú dostupné."
    ),
    "data_available": "road_network (osi ciest I/II/III) — bez železníc a bez priechodov",
    "gap": "železničné línie + polohy priechodov/podchodov; bez nich je verdikt zavádzajúci",
    "law_ref": "§44 ods. 8 písm. d)",
    "never_claims": "jazykové právo (to nie je P-d); bariéra bez dát o priechodoch",
    "gatekeeping": "rizikový indikátor — INSUFFICIENT_DATA môže posunúť na ORANGE, nikdy nie RED",
}


def check_pd(district: dict) -> Verdict:
    district_id = district["id"]
    school_name = district.get("school_name", "")

    # Honest signal of what road data exists near the district (centerlines only).
    class_i_rows = query_sql(f"""
        SELECT count(*) AS n
        FROM skolske_obvody.road_network r
        JOIN skolske_obvody.districts d ON d.id = '{district_id}'
        WHERE r.class IN ('I', 'II')
          AND public.ST_Intersects(r.geom, d.geom)
    """)
    class_i_n = int(class_i_rows[0]["n"]) if class_i_rows else 0

    provenance = {
        "source": "road_network (osi ciest I/II/III, q*) — bez železníc a priechodov",
        "school_name": school_name,
        "class_i_ii_road_segments_in_district": class_i_n,
        "gap": "železničné línie + polohy priechodov/podchodov nie sú v DB",
        "action_required": (
            "Import železníc (OSM railway) a polôh priechodov/podchodov "
            "odblokuje výpočet bariér na trase."
        ),
    }

    evidence = (
        "MÁLO DÁT: chýba dataset bariér (železnice + polohy priechodov/podchodov), "
        "preto sa fyzické bariéry na trase domov→škola nedajú overiť. "
        f"V obvode je {class_i_n} úsek(ov) ciest I/II. triedy, ale bez polôh priechodov "
        "by bol verdikt zavádzajúci. "
        "Indikátor môže posunúť na ORANGE, nikdy nie RED. (P-d sa netýka jazyka.)"
    )

    return Verdict(
        district_id=district_id,
        condition_code="Pd",
        value=V.INSUFFICIENT_DATA,
        confidence=0.0,
        data_completeness=0.0,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
        is_proxy=True,
    )
