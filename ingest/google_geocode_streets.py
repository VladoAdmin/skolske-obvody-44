"""
Sprint G — Google Geocoding API: geocode all VZN streets per district.

For each of the 12 Prešovských obvodov + each street in metadata.streets:
  1. Call Google Geocoding API with "<street>, Prešov, Slovakia"
  2. Parse and upsert result into skolske_obvody.street_geocodes
  3. After all geocoding: build ST_ConcaveHull from geocoded points → districts.geom_google
  4. Report: calls, OK, ZERO_RESULTS, partial_match, cost, Hausdorff distances

Idempotent — uses ON CONFLICT (district_id, street) DO UPDATE.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(GOOGLE_API_KEY|SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/google_geocode_streets.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

from ingest.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, validate_config
from ingest.supabase_client import exec_sql, query_sql

# ── env ──────────────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY", ""))
RATE_SLEEP = 0.05   # 50 RPS limit
MAX_RETRIES = 3


def _check_blockers() -> None:
    if not GOOGLE_API_KEY:
        print("BLOCKER: GOOGLE_API_KEY not set.", file=sys.stderr)
        print("Action: export GOOGLE_API_KEY=<your key> or add it to /host-opt/frantiska-2/.env", file=sys.stderr)
        print("Google Console: enable 'Geocoding API' at https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com", file=sys.stderr)
        sys.exit(2)
    validate_config()


# ── Google Geocoding call ─────────────────────────────────────────────────────

def _geocode_street(street: str) -> dict:
    """
    Call Google Geocoding API for "<street>, Prešov, Slovakia".
    Returns parsed response dict with keys: status, lat, lon, formatted_address,
    bounds_geojson, partial_match, place_type, raw.
    Retries on rate-limit (429 / OVER_QUERY_LIMIT) up to MAX_RETRIES times.
    """
    query = f"{street}, Prešov, Slovakia"
    params = urllib.parse.urlencode({
        "address": query,
        "region": "sk",
        "components": "country:SK|locality:Prešov",
        "key": GOOGLE_API_KEY,
    })
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < MAX_RETRIES:
                wait = 2 ** (attempt + 1)
                print(f"    HTTP {e.code} on '{street}', retry in {wait}s ...")
                time.sleep(wait)
                continue
            return {"status": "REQUEST_DENIED", "raw": {"http_error": e.code}, "query_used": query}
        except Exception as ex:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"status": "INVALID_REQUEST", "raw": {"error": str(ex)}, "query_used": query}

        # Check API-level rate limit in body
        api_status = data.get("status", "UNKNOWN")
        if api_status == "OVER_QUERY_LIMIT" and attempt < MAX_RETRIES:
            wait = 2 ** (attempt + 2)
            print(f"    OVER_QUERY_LIMIT on '{street}', retry in {wait}s ...")
            time.sleep(wait)
            continue

        result: dict = {"status": api_status, "raw": data, "query_used": query}

        if api_status == "OK" and data.get("results"):
            r0 = data["results"][0]
            loc = r0["geometry"]["location"]
            result["lat"] = loc["lat"]
            result["lon"] = loc["lng"]
            result["formatted_address"] = r0.get("formatted_address")
            result["partial_match"] = r0.get("partial_match", False)
            result["place_type"] = r0.get("types", [])
            # viewport bounds as JSONB
            vp = r0["geometry"].get("viewport")
            if vp:
                result["bounds_geojson"] = vp  # dict — will be JSON-encoded in upsert

        return result

    return {"status": "OVER_QUERY_LIMIT", "raw": {}, "query_used": query}


# ── DB upsert ─────────────────────────────────────────────────────────────────

def _upsert_geocode(district_id: str, street: str, geo: dict) -> None:
    """Upsert a single street geocode row via f2_exec_sql."""
    status = geo.get("status", "UNKNOWN")
    lat = geo.get("lat")
    lon = geo.get("lon")
    formatted_address = geo.get("formatted_address")
    partial_match = geo.get("partial_match", False)
    place_type = geo.get("place_type", [])
    bounds_geojson = geo.get("bounds_geojson")
    raw = geo.get("raw", {})
    query_used = geo.get("query_used", "")

    # Geometry
    if lat is not None and lon is not None:
        geom_expr = f"public.ST_SetSRID(public.ST_MakePoint({lon}, {lat}), 4326)"
    else:
        geom_expr = "NULL"

    # Dollar-quote helpers
    def dq(tag: str, val: str) -> str:
        return f"$__{tag}__${val}$__{tag}__$"

    lat_sql = f"{lat}" if lat is not None else "NULL"
    lon_sql = f"{lon}" if lon is not None else "NULL"
    fa_sql = dq("fa", formatted_address) if formatted_address else "NULL"
    pm_sql = "TRUE" if partial_match else "FALSE"
    pt_sql = f"ARRAY[{', '.join(dq('pt' + str(i), t) for i, t in enumerate(place_type))}]::TEXT[]" if place_type else "ARRAY[]::TEXT[]"
    bounds_sql = dq("bg", json.dumps(bounds_geojson, ensure_ascii=False)) + "::jsonb" if bounds_geojson else "NULL"
    raw_sql = dq("raw", json.dumps(raw, ensure_ascii=False)) + "::jsonb"

    sql = f"""
INSERT INTO skolske_obvody.street_geocodes
  (district_id, street, query_used, status, lat, lon, formatted_address,
   bounds_geojson, partial_match, place_type, raw, geom)
VALUES (
  {dq("did", district_id)}::uuid,
  {dq("st", street)},
  {dq("qu", query_used)},
  {dq("sts", status)},
  {lat_sql}, {lon_sql},
  {fa_sql},
  {bounds_sql},
  {pm_sql},
  {pt_sql},
  {raw_sql},
  {geom_expr}
)
ON CONFLICT (district_id, street) DO UPDATE SET
  query_used       = EXCLUDED.query_used,
  status           = EXCLUDED.status,
  lat              = EXCLUDED.lat,
  lon              = EXCLUDED.lon,
  formatted_address= EXCLUDED.formatted_address,
  bounds_geojson   = EXCLUDED.bounds_geojson,
  partial_match    = EXCLUDED.partial_match,
  place_type       = EXCLUDED.place_type,
  raw              = EXCLUDED.raw,
  geom             = EXCLUDED.geom
"""
    result = exec_sql(sql)
    if not result.get("ok"):
        msg = result.get("message", "unknown error")
        print(f"    UPSERT ERROR for '{street}': {msg}")


# ── Hull building ─────────────────────────────────────────────────────────────

def _build_hulls() -> None:
    """Build ST_ConcaveHull from geocoded points and store in districts.geom_google."""
    print("\n[Hull building] Computing concave hulls from geocoded points...")

    rows = query_sql("""
        SELECT
            d.id,
            d.name,
            COUNT(sg.id) FILTER (WHERE sg.status = 'OK') AS ok_count,
            d.geom_google IS NOT NULL AS has_google_geom
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        LEFT JOIN skolske_obvody.street_geocodes sg ON sg.district_id = d.id
        WHERE m.slug = 'presov'
        GROUP BY d.id, d.name, d.geom_google
        ORDER BY d.name
    """)

    for row in rows:
        district_id = row["id"]
        name = row["name"]
        ok_count = int(row.get("ok_count") or 0)

        if ok_count < 3:
            print(f"  {name}: only {ok_count} OK points — skipping hull (need ≥3)")
            continue

        # Build concave hull: target_percent=0.3, allow_holes=true
        hull_sql = f"""
UPDATE skolske_obvody.districts
SET
  geom_google = (
    SELECT public.ST_Multi(
             public.ST_ConcaveHull(
               public.ST_Collect(sg.geom),
               0.3,
               true
             )
           )
    FROM skolske_obvody.street_geocodes sg
    WHERE sg.district_id = $_did_${district_id}$_did_$::uuid
      AND sg.status = 'OK'
      AND sg.geom IS NOT NULL
  ),
  geom_google_metadata = (
    SELECT jsonb_build_object(
      'ok_points', COUNT(*),
      'partial_match_points', COUNT(*) FILTER (WHERE sg.partial_match),
      'built_at', now()::text
    )
    FROM skolske_obvody.street_geocodes sg
    WHERE sg.district_id = $_did2_${district_id}$_did2_$::uuid
      AND sg.status = 'OK'
  )
WHERE id = $_did3_${district_id}$_did3_$::uuid
"""
        result = exec_sql(hull_sql)
        if result.get("ok"):
            print(f"  {name}: hull built from {ok_count} points ✓")
        else:
            print(f"  {name}: hull ERROR — {result.get('message', '?')}")


# ── Hausdorff distance report ─────────────────────────────────────────────────

def _hausdorff_report() -> list[dict]:
    """Compute Hausdorff distance between OSM hull and Google hull per district."""
    print("\n[Hausdorff] Computing OSM vs Google hull divergence...")
    rows = query_sql("""
        SELECT
            d.name,
            CASE
              WHEN d.geom IS NOT NULL AND d.geom_google IS NOT NULL
              THEN round(public.ST_HausdorffDistance(
                     public.ST_Transform(d.geom::public.geometry, 32634),
                     public.ST_Transform(d.geom_google::public.geometry, 32634)
                   )::numeric, 1)
              ELSE NULL
            END AS hausdorff_m
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        ORDER BY hausdorff_m DESC NULLS LAST
    """)
    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _check_blockers()

    print("=" * 64)
    print("Sprint G — Google Geocoding streets → concave hull")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 64)

    # Load all districts + streets
    districts = query_sql("""
        SELECT d.id, d.name, d.metadata->>'streets' AS streets_json
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        ORDER BY d.name
    """)

    # Build full (district_id, street) pairs
    pairs: list[tuple[str, str, str]] = []  # (district_id, district_name, street)
    for d in districts:
        streets = json.loads(d["streets_json"]) if d.get("streets_json") else []
        for s in streets:
            if s and s.strip():
                pairs.append((d["id"], d["name"], s.strip()))

    total = len(pairs)
    cost_estimate = total * 5 / 1000
    print(f"Districts: {len(districts)}, Streets to geocode: {total}")
    print(f"Estimated cost: ${cost_estimate:.2f} USD")
    print()

    # Check what's already done (idempotency)
    already_done = query_sql("""
        SELECT sg.district_id || '_' || sg.street AS key
        FROM skolske_obvody.street_geocodes sg
        JOIN skolske_obvody.districts d ON d.id = sg.district_id
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        LIMIT 10000
    """)
    done_keys = {r["key"] for r in already_done}
    pending = [(did, dname, st) for did, dname, st in pairs if f"{did}_{st}" not in done_keys]
    print(f"Already done: {len(done_keys)}, Pending: {len(pending)}")

    # Stats
    stats = {"ok": 0, "zero": 0, "partial": 0, "error": 0, "calls": 0}

    current_district = None
    for i, (district_id, district_name, street) in enumerate(pending, 1):
        if district_name != current_district:
            current_district = district_name
            print(f"\n[District] {district_name}")

        geo = _geocode_street(street)
        stats["calls"] += 1
        st = geo.get("status", "UNKNOWN")

        if st == "OK":
            stats["ok"] += 1
            if geo.get("partial_match"):
                stats["partial"] += 1
        elif st == "ZERO_RESULTS":
            stats["zero"] += 1
        else:
            stats["error"] += 1

        _upsert_geocode(district_id, street, geo)

        if i % 10 == 0:
            pct = (i / len(pending)) * 100 if pending else 100
            print(f"  Progress: {i}/{len(pending)} ({pct:.0f}%) — OK:{stats['ok']} ZERO:{stats['zero']} ERR:{stats['error']}")

        time.sleep(RATE_SLEEP)

    # Also count already-done stats from DB
    final_stats = query_sql("""
        SELECT
            sg.status,
            COUNT(*) as cnt,
            COUNT(*) FILTER (WHERE sg.partial_match) as partial_cnt
        FROM skolske_obvody.street_geocodes sg
        JOIN skolske_obvody.districts d ON d.id = sg.district_id
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        GROUP BY sg.status
    """)

    print("\n" + "=" * 64)
    print("GEOCODING COMPLETE")
    print("=" * 64)
    print(f"This run: calls={stats['calls']}, OK={stats['ok']}, ZERO={stats['zero']}, partial={stats['partial']}, other={stats['error']}")
    print(f"Estimated cost this run: ${stats['calls'] * 5 / 1000:.2f} USD")
    print("\nDB totals:")
    total_ok = 0
    total_partial = 0
    for row in final_stats:
        print(f"  {row['status']}: {row['cnt']} (partial: {row.get('partial_cnt', 0)})")
        if row["status"] == "OK":
            total_ok = int(row["cnt"])
            total_partial = int(row.get("partial_cnt", 0) or 0)

    # Build hulls
    _build_hulls()

    # Hausdorff report
    hd_rows = _hausdorff_report()
    print("\nHausdorff distances OSM hull vs Google hull (top divergence first):")
    for row in hd_rows:
        hd = row.get("hausdorff_m")
        hd_str = f"{hd} m" if hd is not None else "N/A (no hull yet)"
        print(f"  {row['name']}: {hd_str}")

    print("\n" + "=" * 64)
    print("SUMMARY")
    print("=" * 64)
    print(f"Total geocoded OK: {total_ok}")
    print(f"Partial matches: {total_partial}")
    if hd_rows:
        top3 = [r for r in hd_rows if r.get("hausdorff_m") is not None][:3]
        print("Top 3 Hausdorff distances (biggest OSM→Google correction):")
        for i, r in enumerate(top3, 1):
            print(f"  {i}. {r['name']}: {r['hausdorff_m']} m")
    print(f"Finished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
