"""
VLA-17 — 5 najdlhších peších trás na obvod + prímestská doprava.

Comparison/overview only — NO threshold or verdict. § 44 ods. 8 sets no
numeric distance limit; this script never computes PASS/FAIL, only ranks.

For each of the 12 Prešov districts:
  1. Candidates = skolske_obvody.street_geocodes (status='OK', real
     Google-geocoded VZN street points) UNION shared-municipality centroids
     (districts.metadata->'shared_municipalities' — the grades 5-9 pooled
     catchment, e.g. ZŠ Bajkalská; real polygon centroid from
     skolske_obvody.municipalities.geom, WFS-sourced).
  2. Call Google Routes API v2 (computeRoutes, travelMode=WALK) origin ->
     district's school for EVERY candidate. A candidate whose route comes
     back empty/error is DROPPED from ranking, never guessed via
     straight-line distance.
  3. Rank successful candidates by real distance_m descending, keep top 5.
  4. For any of the top 5 whose origin is a shared_municipality, additionally
     call computeRoutes (travelMode=TRANSIT) for the "prímestská doprava"
     alternative shown in the map popup.
  5. Decode each route's encoded overview polyline into a PostGIS LINESTRING
     and upsert into skolske_obvody.district_longest_routes (existing rows
     for the district are replaced — idempotent, re-runnable).

NOTE: the classic Directions API (maps/api/directions/json) is NOT enabled
on this Google Cloud project — confirmed live (REQUEST_DENIED, "legacy API
... not enabled"). This script uses the newer Routes API v2
(routes.googleapis.com/directions/v2:computeRoutes, POST + X-Goog-FieldMask),
verified live for both WALK and TRANSIT before writing this script.

BUDGET DISCIPLINE — real paid API, ~EUR10 demo cap approved by Vlado
(2026-06-26). Prints candidate/call counts + a rough cost estimate BEFORE any
network call. Refuses to proceed if the estimate would meaningfully exceed
the cap. Cost assumption: $5/1000 for WALK (Routes API Essentials tier, same
rate ingest/google_geocode_streets.py uses for Geocoding) and a conservative
$10/1000 for TRANSIT (Preferred-tier fields such as transitDetails may cost
more than Essentials — exact current SKU boundary not independently
confirmed, so the higher rate is used to avoid under-estimating).

Run:
    source <(grep -E '^(GOOGLE_API_KEY|SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' .env.local | sed 's/^/export /')
    python3 scripts/compute_longest_routes.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import unicodedata
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.config import validate_config  # noqa: E402
from ingest.supabase_client import exec_sql, query_sql  # noqa: E402

# ── env / constants ─────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY", ""))
RATE_SLEEP = 0.05      # 50 RPS limit, matches ingest/google_geocode_streets.py
MAX_RETRIES = 3
TOP_N = 5
COST_PER_1000_WALK_USD = 5.0
COST_PER_1000_TRANSIT_USD = 10.0  # conservative — see module docstring
BUDGET_CAP_EUR = 10.0
BUDGET_STOP_THRESHOLD_USD = 8.0  # safety margin under the ~EUR10 cap
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = (
    "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline,"
    "routes.legs.steps.travelMode,routes.legs.steps.transitDetails"
)
TRAVEL_MODE = {"walking": "WALK", "transit": "TRANSIT"}


def _check_blockers() -> None:
    if not GOOGLE_API_KEY:
        print("BLOCKER: GOOGLE_API_KEY not set.", file=sys.stderr)
        print("Action: source .env.local (see module docstring) before running.", file=sys.stderr)
        sys.exit(2)
    validate_config()


def _parse_duration_seconds(duration: Optional[str]) -> Optional[float]:
    """Parse a Routes API duration string like '1470s' into seconds."""
    if not duration or not duration.endswith("s"):
        return None
    try:
        return float(duration[:-1])
    except ValueError:
        return None


# ── Google Routes API v2 call ───────────────────────────────────────────────

def _directions(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, mode: str) -> dict:
    """
    Call Google Routes API v2 (computeRoutes). Returns dict with keys:
      status ('ok' | 'low_data' | 'unavailable'), distance_m, duration_s,
      polyline, transit_line, query_used, raw_status, attempts.
    NEVER fabricates a straight-line distance — no route (HTTP 200, empty
    body, verified live) -> low_data; any non-2xx or network failure ->
    unavailable.
    `attempts` is the number of HTTP requests actually sent (1 + retries) —
    each is separately billable, so callers must count it, not a flat 1,
    toward the printed cost estimate.
    """
    query_used = f"{origin_lat},{origin_lon} -> {dest_lat},{dest_lon} (mode={mode})"
    body = json.dumps({
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lon}}},
        "travelMode": TRAVEL_MODE[mode],
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    attempts = 0
    for attempt in range(MAX_RETRIES + 1):
        attempts += 1
        try:
            req = urllib.request.Request(ROUTES_URL, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < MAX_RETRIES:
                wait = 2 ** (attempt + 1)
                print(f"    HTTP {e.code}, retry in {wait}s ...")
                time.sleep(wait)
                continue
            return {"status": "unavailable", "raw_status": f"HTTP_{e.code}", "query_used": query_used, "attempts": attempts}
        except Exception as ex:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"status": "unavailable", "raw_status": str(ex), "query_used": query_used, "attempts": attempts}

        routes = data.get("routes")
        if not routes:
            # Verified live: HTTP 200 + {} body for a genuinely unroutable pair.
            return {"status": "low_data", "raw_status": "NO_ROUTES", "query_used": query_used, "attempts": attempts}

        route = routes[0]
        distance = route.get("distanceMeters")
        duration = _parse_duration_seconds(route.get("duration"))
        if distance is None or duration is None:
            return {"status": "low_data", "raw_status": "MISSING_FIELDS", "query_used": query_used, "attempts": attempts}

        transit_line = None
        if mode == "transit":
            steps = (route.get("legs") or [{}])[0].get("steps", [])
            for step in steps:
                if step.get("travelMode") == "TRANSIT" and step.get("transitDetails"):
                    line = step["transitDetails"].get("transitLine", {})
                    vehicle = ((line.get("vehicle") or {}).get("name") or {}).get("text")
                    name = line.get("nameShort") or line.get("name")
                    transit_line = " ".join(p for p in [vehicle, name] if p) or None
                    break

        return {
            "status": "ok",
            "raw_status": "OK",
            "distance_m": round(distance),
            "duration_s": round(duration),
            "polyline": (route.get("polyline") or {}).get("encodedPolyline"),
            "transit_line": transit_line,
            "query_used": query_used,
            "attempts": attempts,
        }

    return {"status": "unavailable", "raw_status": "MAX_RETRIES", "query_used": query_used, "attempts": attempts}


# ── Polyline decode (standard Google encoded-polyline algorithm) ───────────

def _decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google encoded polyline into a list of (lon, lat) tuples."""
    points: list[tuple[float, float]] = []
    index = lat = lng = 0
    length = len(encoded)
    while index < length:
        result = shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        result = shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append((lng / 1e5, lat / 1e5))
    return points


def _linestring_wkt(coords: list[tuple[float, float]]) -> Optional[str]:
    if len(coords) < 2:
        return None
    pts = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"LINESTRING({pts})"


# ── Candidate loading ────────────────────────────────────────────────────────

def _clean_municipality_name(raw: str) -> str:
    """VZN-parser artifact: last item in a shared_municipalities list keeps a
    trailing sentence-ending period, e.g. 'Uzovce .' -> 'Uzovce'."""
    return raw.strip().rstrip(".").strip()


def _strip_diacritics(s: str) -> str:
    """Python-side mirror of Postgres unaccent(), for comparing which cleaned
    input names matched a DB row vs. which had no match at all."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _load_districts() -> list[dict]:
    return query_sql("""
        SELECT
            d.id, d.name,
            public.ST_X(s.geom) AS school_lon, public.ST_Y(s.geom) AS school_lat,
            d.metadata->'shared_municipalities' AS shared_municipalities_json
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.schools s ON s.id = d.school_id
        ORDER BY d.name
    """)


def _load_street_geocode_candidates(district_id: str) -> list[dict]:
    rows = query_sql(f"""
        SELECT id, street AS label, lat, lon
        FROM skolske_obvody.street_geocodes
        WHERE district_id = {_dq(district_id)}::uuid AND status = 'OK'
        ORDER BY street
    """)
    for r in rows:
        r["origin_kind"] = "street_geocode"
    return rows


def _load_shared_municipality_candidates(district_name: str, shared_names_raw: list[str]) -> list[dict]:
    if not shared_names_raw:
        return []
    cleaned = [_clean_municipality_name(n) for n in shared_names_raw if n and n.strip()]
    if not cleaned:
        return []
    # Matched via unaccent() — the VZN-parsed name and the WFS municipalities
    # table disagree on diacritics for at least one real name ("Dulová Ves"
    # vs "Dulova Ves"); exact matching silently drops those candidates.
    placeholders = ",".join(f"unaccent({_dq(n)})" for n in cleaned)
    rows = query_sql(f"""
        SELECT id, name AS label,
               public.ST_Y(public.ST_Centroid(geom)) AS lat,
               public.ST_X(public.ST_Centroid(geom)) AS lon
        FROM skolske_obvody.municipalities
        WHERE unaccent(name) IN ({placeholders}) AND geom IS NOT NULL
        ORDER BY name
    """)
    matched_unaccented = {_strip_diacritics(r["label"]) for r in rows}
    for missing in cleaned:
        if _strip_diacritics(missing) not in matched_unaccented:
            print(f"    WARNING: shared municipality '{missing}' ({district_name}) has no match "
                  f"in skolske_obvody.municipalities even after unaccent() — dropped as a candidate")
    for r in rows:
        r["origin_kind"] = "shared_municipality"
    return rows


# ── DB upsert ─────────────────────────────────────────────────────────────────

def _dq(val: str) -> str:
    """
    Dollar-quote a SQL string value with a fresh random tag.

    f2_exec_sql/f2_query_sql (ingest/supabase_client.py) take a single raw
    SQL string over PostgREST RPC — there is no native bind-parameter
    support to hand off to, so a per-call random tag is the equivalent of a
    parameterized placeholder here: unlike a fixed tag reused across calls,
    a value can never contain (and thus cannot break out of) a tag it had
    no way to predict.
    """
    for _ in range(8):
        tag = f"$__q{uuid.uuid4().hex}__$"
        if tag not in val:
            return f"{tag}{val}{tag}"
    raise ValueError("could not generate a collision-free SQL dollar-quote tag")


def _replace_district_routes(district_id: str, ranked: list[dict]) -> None:
    """Delete this district's existing routes, insert the fresh top-N.
    Re-run-safe: a re-run with fewer successful routes than last time must
    not leave stale higher-rank rows behind."""
    del_sql = f"DELETE FROM skolske_obvody.district_longest_routes WHERE district_id = {_dq(district_id)}::uuid"
    result = exec_sql(del_sql)
    if not result.get("ok"):
        print(f"    DELETE ERROR: {result.get('message')}")
        return

    for row in ranked:
        origin_geom = f"public.ST_SetSRID(public.ST_MakePoint({row['lon']}, {row['lat']}), 4326)"
        route_geom = f"public.ST_SetSRID(public.ST_GeomFromText({_dq(row['route_wkt'])}), 4326)"

        transit_status_sql = _dq(row["transit_status"]) if row.get("transit_status") else "NULL"
        transit_dist_sql = row["transit_distance_m"] if row.get("transit_distance_m") is not None else "NULL"
        transit_dur_sql = row["transit_duration_s"] if row.get("transit_duration_s") is not None else "NULL"
        transit_geom_sql = (
            f"public.ST_SetSRID(public.ST_GeomFromText({_dq(row['transit_route_wkt'])}), 4326)"
            if row.get("transit_route_wkt") else "NULL"
        )
        transit_line_sql = _dq(row["transit_line"]) if row.get("transit_line") else "NULL"

        provenance = json.dumps({
            "source": "Google Maps Directions API (walking)",
            "google_status": row.get("raw_status"),
            "query_used": row.get("query_used"),
            "origin_kind": row["origin_kind"],
        }, ensure_ascii=False)

        sql = f"""
INSERT INTO skolske_obvody.district_longest_routes
  (district_id, rank, origin_kind, origin_label, origin_geom, distance_m,
   duration_s, route_geom, transit_status, transit_distance_m,
   transit_duration_s, transit_geom, transit_line, provenance)
VALUES (
  {_dq(district_id)}::uuid,
  {row['rank']},
  {_dq(row['origin_kind'])},
  {_dq(row['label'])},
  {origin_geom},
  {row['distance_m']},
  {row['duration_s']},
  {route_geom},
  {transit_status_sql},
  {transit_dist_sql},
  {transit_dur_sql},
  {transit_geom_sql},
  {transit_line_sql},
  {_dq(provenance)}::jsonb
)
"""
        result = exec_sql(sql)
        if not result.get("ok"):
            print(f"    INSERT ERROR (rank {row['rank']}): {result.get('message')}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _check_blockers()

    print("=" * 72)
    print("VLA-17 — 5 najdlhších peších trás na obvod")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 72)

    districts = _load_districts()

    # ---- Budget estimate BEFORE any network call ----
    total_walking_calls = 0
    per_district_candidates: dict[str, list[dict]] = {}
    for d in districts:
        street_cands = _load_street_geocode_candidates(d["id"])
        shared_raw = d.get("shared_municipalities_json") or []
        shared_cands = _load_shared_municipality_candidates(d["name"], shared_raw)
        cands = street_cands + shared_cands
        per_district_candidates[d["id"]] = cands
        total_walking_calls += len(cands)

    max_transit_calls = sum(
        len([c for c in cands if c["origin_kind"] == "shared_municipality"])
        for cands in per_district_candidates.values()
    )
    # Worst case: every shared-municipality candidate makes the top 5.
    worst_case_calls = total_walking_calls + max_transit_calls
    worst_case_cost_usd = (
        total_walking_calls * COST_PER_1000_WALK_USD / 1000
        + max_transit_calls * COST_PER_1000_TRANSIT_USD / 1000
    )

    print(f"\nDistricts: {len(districts)}")
    print(f"Walking candidates (street_geocodes + shared-municipality centroids): {total_walking_calls}")
    print(f"Shared-municipality candidates (upper bound on transit calls): {max_transit_calls}")
    print(f"Worst-case total Google Routes API calls: {worst_case_calls}")
    print(f"Worst-case estimated cost: ${worst_case_cost_usd:.2f} USD (~EUR{worst_case_cost_usd * 0.93:.2f}) "
          f"@ ${COST_PER_1000_WALK_USD}/1000 walking + ${COST_PER_1000_TRANSIT_USD}/1000 transit, "
          f"cap ~EUR{BUDGET_CAP_EUR}")

    if worst_case_cost_usd > BUDGET_STOP_THRESHOLD_USD:
        print(f"\nSTOP: worst-case estimate exceeds the ${BUDGET_STOP_THRESHOLD_USD} safety threshold.")
        print("Not running. Report these numbers back before proceeding.")
        sys.exit(3)

    print("\nProceeding — estimate is within budget.\n")

    # ---- Walking routes for every candidate ----
    stats = {"ok": 0, "low_data": 0, "unavailable": 0, "calls": 0, "walk_calls": 0, "transit_calls": 0}
    for d in districts:
        district_id = d["id"]
        school_lat, school_lon = d["school_lat"], d["school_lon"]
        cands = per_district_candidates[district_id]
        print(f"[District] {d['name']} — {len(cands)} candidates")

        successful: list[dict] = []
        for c in cands:
            res = _directions(c["lat"], c["lon"], school_lat, school_lon, "walking")
            stats["calls"] += res["attempts"]
            stats["walk_calls"] += res["attempts"]
            stats[res["status"]] = stats.get(res["status"], 0) + 1
            if res["status"] == "ok":
                c["distance_m"] = res["distance_m"]
                c["duration_s"] = res["duration_s"]
                c["polyline"] = res["polyline"]
                c["raw_status"] = res["raw_status"]
                c["query_used"] = res["query_used"]
                successful.append(c)
            time.sleep(RATE_SLEEP)

        successful.sort(key=lambda c: c["distance_m"], reverse=True)
        top5 = successful[:TOP_N]
        if len(top5) < TOP_N:
            print(f"    WARNING: only {len(top5)}/{TOP_N} routes computed for {d['name']} "
                  f"({len(cands) - len(successful)} candidates dropped as low_data/unavailable)")

        # ---- Transit alternative for shared-municipality entries in the top 5 ----
        ranked_rows = []
        for rank, c in enumerate(top5, start=1):
            route_wkt = _linestring_wkt(_decode_polyline(c["polyline"])) if c.get("polyline") else None
            if not route_wkt:
                print(f"    SKIP rank {rank} ({c['label']}): polyline missing/undecodable")
                continue

            row = {
                "rank": rank,
                "origin_kind": c["origin_kind"],
                "label": c["label"],
                "lat": c["lat"],
                "lon": c["lon"],
                "distance_m": c["distance_m"],
                "duration_s": c["duration_s"],
                "route_wkt": route_wkt,
                "raw_status": c["raw_status"],
                "query_used": c["query_used"],
            }

            if c["origin_kind"] == "shared_municipality":
                tr = _directions(c["lat"], c["lon"], school_lat, school_lon, "transit")
                stats["calls"] += tr["attempts"]
                stats["transit_calls"] += tr["attempts"]
                stats[tr["status"]] = stats.get(tr["status"], 0) + 1
                row["transit_status"] = tr["status"]
                if tr["status"] == "ok":
                    row["transit_distance_m"] = tr["distance_m"]
                    row["transit_duration_s"] = tr["duration_s"]
                    row["transit_line"] = tr.get("transit_line")
                    row["transit_route_wkt"] = (
                        _linestring_wkt(_decode_polyline(tr["polyline"])) if tr.get("polyline") else None
                    )
                time.sleep(RATE_SLEEP)

            ranked_rows.append(row)

        _replace_district_routes(district_id, ranked_rows)
        print(f"    Stored {len(ranked_rows)} routes for {d['name']}")

    print("\n" + "=" * 72)
    print("COMPUTATION COMPLETE")
    print("=" * 72)
    print(f"Total Google Routes API calls made: {stats['calls']} "
          f"(walk: {stats['walk_calls']}, transit: {stats['transit_calls']})")
    print(f"  ok: {stats.get('ok', 0)}  low_data: {stats.get('low_data', 0)}  unavailable: {stats.get('unavailable', 0)}")
    actual_cost_usd = (
        stats["walk_calls"] * COST_PER_1000_WALK_USD / 1000
        + stats["transit_calls"] * COST_PER_1000_TRANSIT_USD / 1000
    )
    print(f"Actual cost: ${actual_cost_usd:.2f} USD (~EUR{actual_cost_usd * 0.93:.2f})")

    final = query_sql("""
        SELECT d.name, COUNT(r.id) AS n_routes,
               COUNT(r.id) FILTER (WHERE r.origin_kind = 'shared_municipality') AS n_shared,
               COUNT(r.id) FILTER (WHERE r.transit_status = 'ok') AS n_transit_ok
        FROM skolske_obvody.districts d
        LEFT JOIN skolske_obvody.district_longest_routes r ON r.district_id = d.id
        GROUP BY d.name ORDER BY d.name
    """)
    print("\nPer-district result:")
    for row in final:
        print(f"  {row['name']}: {row['n_routes']} routes "
              f"({row['n_shared']} shared-municipality, {row['n_transit_ok']} with transit)")

    print(f"\nFinished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
