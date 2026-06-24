"""
P-b — Vzdialenosť/dochádzka (Walking distance via OSRM).

METHODOLOGY §P-b:
  Sample 5–20 representative points per district (centroid + building centroids).
  Call OSRM /route/v1/walking for each sample point → assigned school.
  Compute median distance (m) and median duration (s).

  ZŠ 1. stupeň thresholds:
    PASS  = median ≤ 2 000 m AND ≤ 1 800 s (30 min)
    RISK  = median ≤ 4 000 m  (or >30 min but ≤ 4 km)
    FAIL  = median > 4 000 m
    INCOMPLETE = school_id NULL or no buildings to sample

  Confidence based on sample size: 1 point = 0.3, 5 = 0.55, 10+ = 0.7.
  data_completeness reflects missing children weights (REGOB GAP).

  Never claims exact count of affected children (REGOB unavailable).
"""

from __future__ import annotations

import json
import statistics
import urllib.request
import urllib.error
from typing import Optional

from engine.constants import (
    V, METHODOLOGY_VERSION,
    PB_PASS_DISTANCE_M, PB_PASS_DURATION_S, PB_RISK_DISTANCE_M,
)
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

OSRM_URL = "http://osrm-sk:5000"
MIN_SAMPLES = 5
MAX_SAMPLES = 20

_METHODOLOGY = {
    "rule": "Pb-walking-osrm",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Pešia trasa z reprezentatívnych bodov obvodu (centroid + vzorka budov) "
        "do pridelenej školy cez OSRM walking profil nad OSM SK."
    ),
    "threshold_zs_1st_stage_m": PB_PASS_DISTANCE_M,
    "threshold_zs_1st_stage_s": PB_PASS_DURATION_S,
    "threshold_risk_m": PB_RISK_DISTANCE_M,
    "law_ref": "§44 ods. 8 písm. b)",
    "never_claims": "presný počet dotknutých detí (REGOB GAP — výsledok nie je vážený počtom detí)",
    "caveat": "chýbajúce chodníky/povrch v OSM môže podceňovať skutočnú pešiu trasu",
}


def _osrm_route(origin_lon: float, origin_lat: float,
                dest_lon: float, dest_lat: float) -> Optional[dict]:
    """Call OSRM walking route. Returns {distance_m, duration_s} or None on error."""
    url = (
        f"{OSRM_URL}/route/v1/walking/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        f"?overview=false"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            return {
                "distance_m": route["distance"],
                "duration_s": route["duration"],
            }
    except Exception:
        pass
    return None


def _sample_points(district_id: str, n: int = MAX_SAMPLES) -> list[dict]:
    """
    Get sample points: centroid of district + building centroids inside district.
    Uses mrk_buildings centroids if available, otherwise just district centroid.
    """
    points = []

    # 1. District centroid (always)
    centroid_rows = query_sql(f"""
        SELECT public.ST_X(public.ST_Centroid(geom)) as lon,
               public.ST_Y(public.ST_Centroid(geom)) as lat
        FROM skolske_obvody.districts
        WHERE id = '{district_id}'
    """)
    if centroid_rows:
        points.append({
            "lon": float(centroid_rows[0]["lon"]),
            "lat": float(centroid_rows[0]["lat"]),
            "source": "district_centroid",
        })

    # 2. Address points inside district (if any)
    ap_rows = query_sql(f"""
        SELECT public.ST_X(geom) as lon, public.ST_Y(geom) as lat
        FROM skolske_obvody.address_points
        WHERE district_id = '{district_id}'
        ORDER BY random()
        LIMIT {n - 1}
    """)
    for r in ap_rows:
        points.append({"lon": float(r["lon"]), "lat": float(r["lat"]), "source": "address_point"})

    # 3. If still need more, try MRK buildings inside district
    if len(points) < n:
        needed = n - len(points)
        bld_rows = query_sql(f"""
            SELECT public.ST_X(public.ST_Centroid(b.geom)) as lon,
                   public.ST_Y(public.ST_Centroid(b.geom)) as lat
            FROM skolske_obvody.mrk_buildings b
            JOIN skolske_obvody.districts d ON d.id = '{district_id}'
            WHERE public.ST_Within(b.geom, d.geom)
            ORDER BY random()
            LIMIT {needed}
        """)
        for r in bld_rows:
            points.append({"lon": float(r["lon"]), "lat": float(r["lat"]), "source": "mrk_building"})

    return points[:n]


def check_pb(district: dict) -> Verdict:
    district_id = district["id"]
    school_id = district.get("school_id")
    school_type = district.get("school_type", "ZS")

    if not school_id:
        return Verdict(
            district_id=district_id,
            condition_code="Pb",
            value=V.INCOMPLETE,
            confidence=0.0,
            data_completeness=0.0,
            provenance={"reason": "school_id IS NULL — vzdialenosť nepočítaná"},
            methodology=_METHODOLOGY,
            evidence_text="NEÚPLNÉ: k obvodu nie je priradená škola (school_id = NULL).",
        )

    # Get school location
    school_rows = query_sql(f"""
        SELECT public.ST_X(geom) as lon, public.ST_Y(geom) as lat, name
        FROM skolske_obvody.schools
        WHERE id = '{school_id}'
    """)
    if not school_rows or not school_rows[0].get("lon"):
        return Verdict(
            district_id=district_id,
            condition_code="Pb",
            value=V.INCOMPLETE,
            confidence=0.0,
            data_completeness=0.0,
            provenance={"reason": "school geom IS NULL — vzdialenosť nepočítaná"},
            methodology=_METHODOLOGY,
            evidence_text="NEÚPLNÉ: poloha školy (geom) nie je v DB.",
        )

    school_lon = float(school_rows[0]["lon"])
    school_lat = float(school_rows[0]["lat"])
    school_name = school_rows[0].get("name", "")

    # Sample origin points
    sample_pts = _sample_points(district_id, MAX_SAMPLES)
    if not sample_pts:
        return Verdict(
            district_id=district_id,
            condition_code="Pb",
            value=V.INCOMPLETE,
            confidence=0.0,
            data_completeness=0.0,
            provenance={"reason": "no sample points available"},
            methodology=_METHODOLOGY,
            evidence_text="NEÚPLNÉ: žiadne vzorkovacie body pre obvod.",
        )

    # Call OSRM for each sample point
    results = []
    errors = 0
    for pt in sample_pts:
        route = _osrm_route(pt["lon"], pt["lat"], school_lon, school_lat)
        if route:
            results.append(route)
        else:
            errors += 1

    if not results:
        return Verdict(
            district_id=district_id,
            condition_code="Pb",
            value=V.INCOMPLETE,
            confidence=0.0,
            data_completeness=0.0,
            provenance={
                "reason": "OSRM returned no routes",
                "sample_size": len(sample_pts),
                "errors": errors,
            },
            methodology=_METHODOLOGY,
            evidence_text="NEÚPLNÉ: OSRM nevrátil žiadne trasy pre obvod.",
        )

    distances = [r["distance_m"] for r in results]
    durations = [r["duration_s"] for r in results]
    median_dist = statistics.median(distances)
    median_dur = statistics.median(durations)
    max_dist = max(distances)
    sample_size = len(results)

    # Confidence scales with sample size
    if sample_size >= 10:
        confidence = 0.7
    elif sample_size >= 5:
        confidence = 0.55
    else:
        confidence = 0.3

    # data_completeness: without children weights, not 100%
    data_completeness = min(0.6, confidence * 0.85)

    # Determine value
    if median_dist <= PB_PASS_DISTANCE_M and median_dur <= PB_PASS_DURATION_S:
        value = V.PASS
    elif median_dist <= PB_RISK_DISTANCE_M:
        value = V.RISK
    else:
        value = V.FAIL

    provenance = {
        "source": "OSRM walking (OSM SK)",
        "school_id": school_id,
        "school_name": school_name,
        "school_lon": school_lon,
        "school_lat": school_lat,
        "sample_size": sample_size,
        "sample_errors": errors,
        "median_distance_m": round(median_dist, 1),
        "median_duration_s": round(median_dur, 1),
        "max_distance_m": round(max_dist, 1),
        "threshold_pass_m": PB_PASS_DISTANCE_M,
        "threshold_pass_s": PB_PASS_DURATION_S,
        "threshold_risk_m": PB_RISK_DISTANCE_M,
        "caveat": "not weighted by children count (REGOB GAP)",
        "sample_sources": list({pt["source"] for pt in sample_pts[:sample_size]}),
    }

    evidence = (
        f"{value}: medián pešej vzdialenosti = {round(median_dist)}m "
        f"({round(median_dur/60, 1)} min). "
        f"Max: {round(max_dist)}m. "
        f"Vzorka: {sample_size} bodov. "
        f"Škola: {school_name}. "
        "Výsledok nie je vážený počtom detí (REGOB GAP)."
    )

    return Verdict(
        district_id=district_id,
        condition_code="Pb",
        value=value,
        confidence=confidence,
        data_completeness=data_completeness,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
    )
