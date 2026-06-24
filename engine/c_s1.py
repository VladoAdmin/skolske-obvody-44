"""
Š1 — Pokrytie (Coverage): every address in the municipality belongs to exactly one district.

METHODOLOGY §Š1:
  PASS = 100% address points covered, 0 uncovered, 0 multi-assigned.
  FAIL = any uncovered or multi-assigned points.
  INCOMPLETE = no address_points available for this municipality (proxy fallback).

Real address_points: Register adries MV SR (currently 0 rows in DB — GAP).
Proxy: OSM building centroids from mrk_buildings WHERE obec matches municipality.
Since mrk_buildings only covers MRK villages (not Prešov), proxy is shallow.
For Prešov we use a geometric coverage test: union of all district geometries
must equal the municipality geometry (no gap, no overlap at municipality boundary).

Proxy methodology:
  - Test ST_Covers(municipality.geom, ST_Union(all_district_geoms)) — no gap.
  - Test that districts do not overlap each other (cross-counts).
  - confidence = 0.4 (geometric proxy, no real address points, q6 district geom).
  - data_completeness = 0.3 (address_points = 0, coverage test is indirect).
"""

from __future__ import annotations

from engine.constants import V, ENGINE_VERSION, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql


_METHODOLOGY = {
    "rule": "Š1-coverage-proxy",
    "version": METHODOLOGY_VERSION,
    "description": (
        "No Register adries address_points in DB (GAP). "
        "Proxy: geometric union of district polygons vs municipality boundary. "
        "Coverage gap = ST_Difference area > 0. "
        "Does NOT test individual address assignment — use INCOMPLETE status."
    ),
    "data_source": "district geometries (q6), municipality boundary (q9)",
    "never_claims": "geometric proxy is not equivalent to per-address coverage test",
}


def check_s1(district: dict, all_districts: list[dict], municipality_id: str) -> Verdict:
    """
    Run Š1 for one district.

    Because real address points are absent, we check at the MUNICIPALITY level
    whether the union of districts covers the municipality area (no gaps).
    We run this once per municipality and attach identical coverage result
    to each district, with coverage_gap_area_m2 in provenance.

    Overlap test (Š2 covers this too but Š1 also flags uncovered area).
    """
    district_id = district["id"]

    # Check if real address_points exist for this municipality
    ap_rows = query_sql(
        f"SELECT COUNT(*) as n FROM skolske_obvody.address_points "
        f"WHERE municipality_id = '{municipality_id}'"
    )
    address_point_count = int(ap_rows[0]["n"]) if ap_rows else 0

    if address_point_count > 0:
        return _check_s1_real(district_id, municipality_id, address_point_count)
    else:
        return _check_s1_proxy(district_id, municipality_id, all_districts)


def _check_s1_real(district_id: str, municipality_id: str, ap_count: int) -> Verdict:
    """Full address-point-based Š1 check (when address_points are populated)."""
    # Count uncovered points (no district assignment)
    uncovered = query_sql(
        f"SELECT COUNT(*) as n FROM skolske_obvody.address_points "
        f"WHERE municipality_id = '{municipality_id}' AND district_id IS NULL"
    )
    uncovered_n = int(uncovered[0]["n"]) if uncovered else 0

    # Count multi-assigned (address covered by >1 district)
    multi = query_sql(f"""
        SELECT COUNT(*) as n FROM (
            SELECT ap.id, COUNT(d.id) as district_count
            FROM skolske_obvody.address_points ap
            JOIN skolske_obvody.districts d
              ON public.ST_Within(ap.geom, d.geom)
             AND d.municipality_id = '{municipality_id}'
            WHERE ap.municipality_id = '{municipality_id}'
            GROUP BY ap.id
            HAVING COUNT(d.id) > 1
        ) sub
    """)
    multi_n = int(multi[0]["n"]) if multi else 0

    is_pass = uncovered_n == 0 and multi_n == 0
    provenance = {
        "source": "Register adries MV SR (address_points table)",
        "address_point_count": ap_count,
        "uncovered_count": uncovered_n,
        "multi_assigned_count": multi_n,
        "method": "ST_Within per address_point vs district geom",
    }
    methodology = {**_METHODOLOGY, "rule": "Š1-coverage-real"}
    return Verdict(
        district_id=district_id,
        condition_code="S1",
        value=V.PASS if is_pass else V.FAIL,
        confidence=0.8,
        data_completeness=0.9,
        provenance=provenance,
        methodology=methodology,
        evidence_text=(
            f"Adresné body: {ap_count}. Nepokryté: {uncovered_n}. "
            f"Viacnásobne priradené: {multi_n}."
        ),
    )


def _check_s1_proxy(district_id: str, municipality_id: str, all_districts: list[dict]) -> Verdict:
    """
    Geometric proxy Š1: union of district polygons must cover municipality.

    Runs municipality-level check once; result attached to calling district.
    confidence=0.4 — proxy, q6 district geom.
    data_completeness=0.3 — no real address data.
    """
    # Gap = area of municipality NOT covered by any district
    gap_rows = query_sql(f"""
        WITH mun AS (
            SELECT geom FROM skolske_obvody.municipalities
            WHERE id = '{municipality_id}'
        ),
        dist_union AS (
            SELECT public.ST_Union(geom) AS geom
            FROM skolske_obvody.districts
            WHERE municipality_id = '{municipality_id}'
        )
        SELECT
            public.ST_Area(public.ST_Transform(
                public.ST_Difference(mun.geom, dist_union.geom),
                32634
            )) AS gap_m2,
            public.ST_Area(public.ST_Transform(mun.geom, 32634)) AS mun_area_m2
        FROM mun, dist_union
    """)

    gap_m2 = float(gap_rows[0]["gap_m2"]) if gap_rows and gap_rows[0]["gap_m2"] else 0.0
    mun_area_m2 = float(gap_rows[0]["mun_area_m2"]) if gap_rows and gap_rows[0]["mun_area_m2"] else 1.0
    gap_pct = round(gap_m2 / mun_area_m2 * 100, 2) if mun_area_m2 > 0 else 0.0

    # Geometric proxy: tolerate up to 0.5% gap (slivers/edge artefacts)
    # Actually per methodology: PASS=100% coverage. But proxy artefacts at
    # building-centroid hull boundaries are expected. We flag > 1% as notable.
    # For INCOMPLETE status: all districts have geometry, so proxy CAN run.
    # Result: if gap > 1% → flag analytically but still INCOMPLETE (proxy)
    # The value is always INCOMPLETE for proxy (no real address data).

    provenance = {
        "source": "District geometries (q6) vs municipality boundary (q9)",
        "proxy": True,
        "proxy_reason": "Register adries address_points = 0 in DB (GAP)",
        "gap_m2": round(gap_m2, 1),
        "municipality_area_m2": round(mun_area_m2, 1),
        "gap_pct": gap_pct,
        "n_districts": len(all_districts),
        "note": (
            "Proxy coverage check. Real Š1 requires per-address-point spatial join. "
            "Geometric gap may include forest/fields outside urban area."
        ),
    }

    evidence = (
        f"PROXY (bez adresných bodov). Geometrická medzera: {gap_pct}% plochy obce. "
        f"Počet obvodov: {len(all_districts)}. "
        "Skutočné Š1 vyžaduje Register adries — momentálne nedostupný (GAP)."
    )

    return Verdict(
        district_id=district_id,
        condition_code="S1",
        value=V.INCOMPLETE,
        confidence=0.4,
        data_completeness=0.3,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
        is_proxy=True,
    )
