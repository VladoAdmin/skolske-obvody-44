"""
P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km (air-line distance address → assigned school).

METHODOLOGY §P-a (labels.ts canonical = "Vzdialenosť ZŠ 1. stupeň ≤ 2 km"):
  For each geocoded address assigned to the district, compute the air-line
  (straight-line) distance to the district's assigned school.
  §44 ods. 8 písm. a): a 1st-grade pupil should not have the school more than
  2 km away as the crow flies.

  Value:
    FAIL  = at least one real address is > 2 000 m from the assigned school.
    PASS  = enough geocoded addresses (>= MIN_SAMPLES) and ALL are <= 2 000 m.
    INSUFFICIENT_DATA = fewer than MIN_SAMPLES geocoded addresses in the district
                        (we cannot honestly judge distance from 0–2 points).

  Source: house_geocodes (Register adries → Google geocode), assigned to district
  by district_id. Distance computed in EPSG:32634 (metres).

  This is a risk INDICATOR (Pa ∈ INDICATOR_CONDITIONS): FAIL/INSUFFICIENT_DATA
  can push the semafor to ORANGE but never RED (legal status is Š1–Š3 only).

  DEMO addresses (house_geocodes.is_demo = TRUE) are included so a fabricated
  >2 km address can be demonstrated; the verdict is flagged is_mock=TRUE only
  when the deciding far address is a demo row.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION, PB_PASS_DISTANCE_M
from engine.demo_inputs import DEMO_COMPLETENESS, DEMO_CONFIDENCE, get_demo_input
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

# Minimum geocoded addresses required to make a confident PASS/FAIL judgement.
MIN_SAMPLES = 3

_METHODOLOGY = {
    "rule": "Pa-airline-distance-2km",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Vzdušná (priama) vzdialenosť každej geokódovanej adresy obvodu k pridelenej "
        "škole. Prah pre 1. stupeň ZŠ: 2 km. FAIL = aspoň jedna adresa > 2 km."
    ),
    "threshold_m": PB_PASS_DISTANCE_M,
    "min_samples": MIN_SAMPLES,
    "data_source": "house_geocodes (Register adries + geokódovanie), district geom (q6)",
    "law_ref": "§44 ods. 8 písm. a)",
    "never_claims": "presný počet dotknutých detí; vzdušná čiara nie je pešia trasa (to je P-b)",
    "gatekeeping": "rizikový indikátor — môže posunúť na ORANGE, nikdy nie RED",
}


def check_pa(district: dict) -> Verdict:
    district_id = district["id"]
    school_id = district.get("school_id")
    school_name = district.get("school_name", "")

    # DEMO MODE: complete distance input → decisive PASS/FAIL at the 2 km threshold.
    demo = get_demo_input(district_id)
    if demo is not None and demo.get("pa_max_distance_m") is not None:
        max_m = float(demo["pa_max_distance_m"])
        is_fail = max_m > PB_PASS_DISTANCE_M
        if is_fail:
            evidence = (
                f"FAIL [DEMO]: najvzdialenejšia adresa obvodu je {round(max_m)} m vzdušnou "
                f"čiarou od pridelenej školy {school_name} (prah 2 000 m pre 1. stupeň). "
                "Žiak má školu ďalej než 2 km (§ 44 ods. 8 písm. a). Ukážkové dáta."
            )
        else:
            evidence = (
                f"PASS [DEMO]: najvzdialenejšia adresa obvodu je {round(max_m)} m vzdušnou "
                f"čiarou od školy {school_name} (≤ 2 km). Ukážkové dáta."
            )
        return Verdict(
            district_id=district_id,
            condition_code="Pa",
            value=V.FAIL if is_fail else V.PASS,
            confidence=DEMO_CONFIDENCE,
            data_completeness=DEMO_COMPLETENESS,
            provenance={"source": "DEMO — vzdialenosť adresa→škola (ukážkové dáta)",
                        "demo": True, "max_distance_m": round(max_m, 1),
                        "threshold_m": PB_PASS_DISTANCE_M, "school_name": school_name},
            methodology={**_METHODOLOGY, "rule": "Pa-airline-distance-2km-demo"},
            evidence_text=evidence,
            is_mock=True,
        )

    if not school_id:
        return Verdict(
            district_id=district_id,
            condition_code="Pa",
            value=V.INSUFFICIENT_DATA,
            confidence=0.0,
            data_completeness=0.0,
            provenance={"reason": "school_id IS NULL — vzdialenosť nepočítaná"},
            methodology=_METHODOLOGY,
            evidence_text="MÁLO DÁT: k obvodu nie je priradená škola (school_id = NULL).",
        )

    # Air-line distance (EPSG:32634, metres) from each geocoded address in the
    # district to the assigned school. Include demo rows; expose is_demo per row.
    rows = query_sql(f"""
        SELECT
            h.street, h.house_number,
            COALESCE(h.is_demo, FALSE) AS is_demo,
            public.ST_Distance(
                public.ST_Transform(h.geom, 32634),
                public.ST_Transform(s.geom, 32634)
            ) AS dist_m,
            public.ST_Y(h.geom) AS lat,
            public.ST_X(h.geom) AS lon
        FROM skolske_obvody.house_geocodes h
        JOIN skolske_obvody.schools s ON s.id = '{school_id}'
        WHERE h.district_id = '{district_id}'
          AND h.geom IS NOT NULL
          AND h.valid IS NOT FALSE
          AND s.geom IS NOT NULL
        ORDER BY dist_m DESC
    """)

    n = len(rows)
    if n == 0:
        return Verdict(
            district_id=district_id,
            condition_code="Pa",
            value=V.INSUFFICIENT_DATA,
            confidence=0.0,
            data_completeness=0.0,
            provenance={
                "source": "house_geocodes (Register adries) — žiadne geokódované adresy v obvode",
                "school_name": school_name,
                "threshold_m": PB_PASS_DISTANCE_M,
                "action_required": "Doplniť geokódované adresy obvodu (Register adries) odblokuje P-a.",
            },
            methodology=_METHODOLOGY,
            evidence_text=(
                f"MÁLO DÁT: v obvode nie sú geokódované adresy (Register adries). "
                f"Vzdialenosť k škole {school_name} sa nedá overiť. "
                "Indikátor môže posunúť na ORANGE, nikdy nie RED."
            ),
        )

    farthest = rows[0]
    far_dist = float(farthest["dist_m"])
    far_addr = f"{(farthest['street'] or '').strip()} {(farthest['house_number'] or '').strip()}".strip()
    over_2km = [r for r in rows if float(r["dist_m"]) > PB_PASS_DISTANCE_M]
    n_over = len(over_2km)
    decided_by_demo = bool(farthest["is_demo"]) and far_dist > PB_PASS_DISTANCE_M

    provenance = {
        "source": "house_geocodes (Register adries + geokódovanie)",
        "school_name": school_name,
        "addresses_checked": n,
        "addresses_over_2km": n_over,
        "max_distance_m": round(far_dist, 1),
        "farthest_address": far_addr,
        "farthest_lat": float(farthest["lat"]),
        "farthest_lon": float(farthest["lon"]),
        "farthest_is_demo": bool(farthest["is_demo"]),
        "threshold_m": PB_PASS_DISTANCE_M,
        "method": "ST_Distance vzdušná čiara, EPSG:32634",
    }

    if far_dist > PB_PASS_DISTANCE_M:
        value = V.FAIL
        evidence = (
            f"FAIL: {n_over} z {n} adries je nad 2 km vzdušnou čiarou od pridelenej školy "
            f"{school_name}. Najvzdialenejšia: „{far_addr}“ = {round(far_dist)} m "
            f"(prah 2 000 m)."
            + (" [DEMO adresa]" if decided_by_demo else "")
        )
        return Verdict(
            district_id=district_id,
            condition_code="Pa",
            value=value,
            confidence=0.7,
            data_completeness=min(0.7, 0.3 + n * 0.02),
            provenance=provenance,
            methodology=_METHODOLOGY,
            evidence_text=evidence,
            is_mock=decided_by_demo,
        )

    if n < MIN_SAMPLES:
        return Verdict(
            district_id=district_id,
            condition_code="Pa",
            value=V.INSUFFICIENT_DATA,
            confidence=0.2,
            data_completeness=0.2,
            provenance=provenance,
            methodology=_METHODOLOGY,
            evidence_text=(
                f"MÁLO DÁT: len {n} geokódovaná(é) adresa(y) v obvode (min. {MIN_SAMPLES}). "
                f"Najvzdialenejšia „{far_addr}“ = {round(far_dist)} m (≤ 2 km), "
                "ale vzorka je primalá na spoľahlivý záver."
            ),
        )

    return Verdict(
        district_id=district_id,
        condition_code="Pa",
        value=V.PASS,
        confidence=0.7,
        data_completeness=min(0.7, 0.3 + n * 0.02),
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=(
            f"PASS: všetkých {n} geokódovaných adries je do 2 km vzdušnou čiarou od školy "
            f"{school_name}. Najvzdialenejšia: „{far_addr}“ = {round(far_dist)} m."
        ),
    )
