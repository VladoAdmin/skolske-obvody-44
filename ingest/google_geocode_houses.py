"""
Sprint H — Per-house Google Geocoding.

For each row in vzn_street_ranges where range_type != 'all':
  1. Expand to concrete house numbers.
  2. Geocode via Google Geocoding API:
     "<street> <house_number>, Prešov, Slovakia"
  3. Upsert into house_geocodes.
  4. After geocoding: update districts.geom_google (hull from street + house points).

Caps:
  - max 100 house numbers per street
  - global cap 20 000 API calls (~$100)

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(GOOGLE_API_KEY|SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/google_geocode_houses.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY", ""))

RATE_SLEEP = 0.05       # 50 RPS limit
MAX_RETRIES = 3
MAX_PER_STREET = 100    # cap house numbers per street
GLOBAL_CAP = 20_000     # max total API calls


def _check_blockers() -> None:
    if not GOOGLE_API_KEY:
        print("BLOCKER: GOOGLE_API_KEY not set.", file=sys.stderr)
        sys.exit(2)
    validate_config()


# ---------------------------------------------------------------------------
# Range expansion
# ---------------------------------------------------------------------------

def _expand_numbers(range_type: str, numbers: list[int]) -> list[int]:
    """
    Expand DB numbers array to concrete house numbers.

    range_type='odd':   numbers=[lo,hi] → odd range; or [] → no expansion (skip)
    range_type='even':  numbers=[lo,hi] → even range; or [] → skip
    range_type='range': numbers=[lo,hi,...] → pairs of lo/hi ranges
    range_type='single': numbers=[n,...] → exactly those
    range_type='all':   → [] (skip, street-level sufficient)
    """
    if range_type == 'all':
        return []

    if range_type == 'single':
        return list(numbers)

    if range_type in ('odd', 'even'):
        if len(numbers) < 2:
            # No explicit range — we could enumerate broadly, but spec says skip if too many
            # Do a moderate range: 1-199 odd or 2-200 even
            if range_type == 'odd':
                return list(range(1, 200, 2))  # 100 numbers
            else:
                return list(range(2, 202, 2))  # 100 numbers
        # numbers is a flat list of [lo, hi] pairs (possibly multiple pairs)
        result: list[int] = []
        step = 2
        for i in range(0, len(numbers) - 1, 2):
            lo, hi = numbers[i], numbers[i + 1]
            result.extend(range(lo, hi + 1, step))
        return result

    if range_type == 'range':
        # numbers = flat list of [lo, hi] pairs + singletons
        # We stored them as pairs for ranges, singles as single items
        # Need to detect: pairs are stored as consecutive lo,hi
        result = []
        i = 0
        while i < len(numbers):
            if i + 1 < len(numbers) and numbers[i + 1] > numbers[i] and (numbers[i + 1] - numbers[i]) > 1:
                lo, hi = numbers[i], numbers[i + 1]
                result.extend(range(lo, hi + 1))
                i += 2
            else:
                result.append(numbers[i])
                i += 1
        return result

    return list(numbers)


def _sample_evenly(nums: list[int], cap: int) -> list[int]:
    """Sample up to `cap` numbers evenly from the list."""
    if len(nums) <= cap:
        return nums
    step = len(nums) / cap
    return [nums[int(i * step)] for i in range(cap)]


# ---------------------------------------------------------------------------
# Google Geocoding
# ---------------------------------------------------------------------------

def _geocode_house(street: str, house_number: str) -> dict:
    """
    Call Google Geocoding API for "<street> <house_number>, Prešov, Slovakia".
    Returns parsed result dict.
    """
    query = f"{street} {house_number}, Prešov, Slovakia"
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
                time.sleep(wait)
                continue
            return {"status": "REQUEST_DENIED", "raw": {"http_error": e.code}, "query_used": query}
        except Exception as ex:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"status": "INVALID_REQUEST", "raw": {"error": str(ex)}, "query_used": query}

        api_status = data.get("status", "UNKNOWN")
        if api_status == "OVER_QUERY_LIMIT" and attempt < MAX_RETRIES:
            wait = 2 ** (attempt + 2)
            print(f"    OVER_QUERY_LIMIT, retry in {wait}s ...")
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

        return result

    return {"status": "OVER_QUERY_LIMIT", "raw": {}, "query_used": query}


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def _dq(tag: str, val: str) -> str:
    """Dollar-quote a string value."""
    return f"$__{tag}__${val}$__{tag}__$"


def _upsert_house(district_id: str, street: str, house_number: str, geo: dict) -> None:
    """Upsert single house geocode row."""
    status = geo.get("status", "UNKNOWN")
    lat = geo.get("lat")
    lon = geo.get("lon")
    formatted_address = geo.get("formatted_address")
    partial_match = geo.get("partial_match", False)
    place_type = geo.get("place_type", [])
    raw = geo.get("raw", {})
    query_used = geo.get("query_used", "")

    geom_expr = (
        f"public.ST_SetSRID(public.ST_MakePoint({lon}, {lat}), 4326)"
        if lat is not None and lon is not None
        else "NULL"
    )

    lat_sql = str(lat) if lat is not None else "NULL"
    lon_sql = str(lon) if lon is not None else "NULL"
    fa_sql = _dq("fa", formatted_address) if formatted_address else "NULL"
    pm_sql = "TRUE" if partial_match else "FALSE"
    pt_sql = (
        "ARRAY[" + ", ".join(_dq(f"pt{i}", t) for i, t in enumerate(place_type)) + "]::TEXT[]"
        if place_type else "ARRAY[]::TEXT[]"
    )
    raw_sql = _dq("raw", json.dumps(raw, ensure_ascii=False)) + "::jsonb"

    sql = f"""
INSERT INTO skolske_obvody.house_geocodes
  (district_id, street, house_number, query_used, status, lat, lon,
   formatted_address, partial_match, place_type, raw, geom)
VALUES (
  {_dq("did", district_id)}::uuid,
  {_dq("st", street)},
  {_dq("hn", house_number)},
  {_dq("qu", query_used)},
  {_dq("sts", status)},
  {lat_sql}, {lon_sql},
  {fa_sql},
  {pm_sql},
  {pt_sql},
  {raw_sql},
  {geom_expr}
)
ON CONFLICT (district_id, street, house_number) DO UPDATE SET
  query_used        = EXCLUDED.query_used,
  status            = EXCLUDED.status,
  lat               = EXCLUDED.lat,
  lon               = EXCLUDED.lon,
  formatted_address = EXCLUDED.formatted_address,
  partial_match     = EXCLUDED.partial_match,
  place_type        = EXCLUDED.place_type,
  raw               = EXCLUDED.raw,
  geom              = EXCLUDED.geom
"""
    result = exec_sql(sql)
    if not result.get("ok"):
        print(f"    UPSERT ERROR {street} {house_number}: {result.get('message', '?')}")


# ---------------------------------------------------------------------------
# Hull rebuild
# ---------------------------------------------------------------------------

def _rebuild_hulls() -> None:
    """Rebuild geom_google per district using BOTH street centroids + house points."""
    print("\n[Hull rebuild] Combining street centroids + house points...")

    # Check if ST_ConcaveHull accepts nested ST_Collect by trying a simple approach
    # We use a CTE to union both point sets
    sql = """
UPDATE skolske_obvody.districts d
SET
  geom_google = sub.hull,
  geom_google_metadata = jsonb_build_object(
    'method', 'concave_hull_streets_plus_houses',
    'street_points', sub.street_count,
    'house_points', sub.house_count,
    'updated_at', now()
  )
FROM (
  SELECT
    d2.id AS district_id,
    public.ST_Multi(
      public.ST_ConcaveHull(
        public.ST_Collect(all_geoms.geom),
        0.3,
        true
      )
    ) AS hull,
    SUM(CASE WHEN all_geoms.src = 'street' THEN 1 ELSE 0 END) AS street_count,
    SUM(CASE WHEN all_geoms.src = 'house' THEN 1 ELSE 0 END) AS house_count
  FROM skolske_obvody.districts d2
  JOIN skolske_obvody.municipalities m ON m.id = d2.municipality_id
  CROSS JOIN LATERAL (
    SELECT sg.geom, 'street' AS src
    FROM skolske_obvody.street_geocodes sg
    WHERE sg.district_id = d2.id AND sg.geom IS NOT NULL
    UNION ALL
    SELECT hg.geom, 'house' AS src
    FROM skolske_obvody.house_geocodes hg
    WHERE hg.district_id = d2.id AND hg.geom IS NOT NULL
  ) AS all_geoms
  WHERE m.slug = 'presov'
  GROUP BY d2.id
  HAVING COUNT(all_geoms.geom) >= 3
) sub
WHERE d.id = sub.district_id
"""
    result = exec_sql(sql)
    if result.get("ok"):
        print("  Hull rebuild OK")
    else:
        msg = result.get("message", "?")
        print(f"  Hull rebuild WARNING: {msg}")
        # Fallback: try with street-only hull (Sprint G approach)
        print("  Falling back to street-only hull rebuild...")
        fallback_sql = """
UPDATE skolske_obvody.districts d
SET
  geom_google = (
    SELECT public.ST_Multi(public.ST_ConcaveHull(public.ST_Collect(sg.geom), 0.3, true))
    FROM skolske_obvody.street_geocodes sg
    WHERE sg.district_id = d.id AND sg.geom IS NOT NULL
  ),
  geom_google_metadata = jsonb_build_object(
    'method', 'concave_hull_streets_only_fallback',
    'updated_at', now()
  )
FROM skolske_obvody.municipalities m
WHERE m.id = d.municipality_id AND m.slug = 'presov'
"""
        r2 = exec_sql(fallback_sql)
        if r2.get("ok"):
            print("  Fallback hull rebuild OK")
        else:
            print(f"  Fallback hull ERROR: {r2.get('message', '?')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _check_blockers()

    print("=" * 64)
    print("Sprint H — Per-house Google Geocoding")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 64)

    # Load ranges from DB
    print("\n[Load] Reading vzn_street_ranges from DB...")
    ranges = query_sql("""
        SELECT
            vr.id,
            vr.district_id,
            d.metadata->>'district_number' AS district_num,
            vr.street,
            vr.range_type,
            vr.numbers,
            vr.raw_text
        FROM skolske_obvody.vzn_street_ranges vr
        JOIN skolske_obvody.districts d ON d.id = vr.district_id
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
          AND vr.range_type != 'all'
        ORDER BY d.metadata->>'district_number', vr.street, vr.range_type
    """)
    print(f"  Loaded {len(ranges)} non-all ranges")

    # Build work list: (district_id, street, house_number)
    work: list[tuple[str, str, str]] = []  # (district_id, street, house_number)
    skipped_streets: list[str] = []

    for row in ranges:
        district_id = row['district_id']
        street = row['street']
        range_type = row['range_type']
        raw_nums = row.get('numbers') or []

        # DB returns numbers as list or None
        if isinstance(raw_nums, str):
            try:
                raw_nums = json.loads(raw_nums)
            except Exception:
                raw_nums = []

        nums = _expand_numbers(range_type, raw_nums)
        nums = _sample_evenly(nums, MAX_PER_STREET)

        if not nums:
            skipped_streets.append(f"{row.get('district_num','?')}.{street}({range_type})")
            continue

        for n in nums:
            work.append((district_id, street, str(n)))

    # Deduplicate (same district+street+house from multiple range rows)
    seen: set[tuple[str, str, str]] = set()
    deduped: list[tuple[str, str, str]] = []
    for item in work:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    work = deduped

    print(f"  Work items (unique): {len(work)}")
    if skipped_streets:
        print(f"  Skipped (empty expansion): {len(skipped_streets)}")

    # Check global cap
    if len(work) > GLOBAL_CAP:
        print(f"  WARNING: {len(work)} items exceed cap {GLOBAL_CAP} — sampling down evenly")
        work = _sample_evenly(work, GLOBAL_CAP)
        print(f"  Sampled to: {len(work)} items")

    estimated_cost = len(work) * 5 / 1000
    print(f"  Estimated cost: ${estimated_cost:.2f} USD")

    # Check already done (idempotency)
    already_done_rows = query_sql("""
        SELECT hg.district_id || '_' || hg.street || '_' || hg.house_number AS key
        FROM skolske_obvody.house_geocodes hg
        JOIN skolske_obvody.districts d ON d.id = hg.district_id
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        LIMIT 100000
    """)
    done_keys: set[str] = {r['key'] for r in already_done_rows}

    pending = [(did, st, hn) for did, st, hn in work if f"{did}_{st}_{hn}" not in done_keys]
    print(f"  Already done: {len(done_keys)}, Pending: {len(pending)}")

    # Geocode
    stats = {'ok': 0, 'zero': 0, 'partial': 0, 'error': 0, 'calls': 0}
    prev_street = None

    for i, (district_id, street, house_number) in enumerate(pending, 1):
        if street != prev_street:
            prev_street = street
            print(f"\n  [Street] {street}")

        geo = _geocode_house(street, house_number)
        stats['calls'] += 1
        st = geo.get('status', 'UNKNOWN')

        if st == 'OK':
            stats['ok'] += 1
            if geo.get('partial_match'):
                stats['partial'] += 1
        elif st == 'ZERO_RESULTS':
            stats['zero'] += 1
        else:
            stats['error'] += 1

        _upsert_house(district_id, street, house_number, geo)

        if i % 50 == 0:
            pct = (i / len(pending)) * 100 if pending else 100
            cost_so_far = stats['calls'] * 5 / 1000
            print(f"  Progress: {i}/{len(pending)} ({pct:.0f}%) — OK:{stats['ok']} ZERO:{stats['zero']} ERR:{stats['error']} cost:${cost_so_far:.2f}")

        time.sleep(RATE_SLEEP)

    # Rebuild hulls
    _rebuild_hulls()

    # Final DB stats
    final_stats = query_sql("""
        SELECT
            hg.status,
            COUNT(*) AS cnt,
            COUNT(*) FILTER (WHERE hg.partial_match) AS partial_cnt
        FROM skolske_obvody.house_geocodes hg
        JOIN skolske_obvody.districts d ON d.id = hg.district_id
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        GROUP BY hg.status
    """)

    top_districts = query_sql("""
        SELECT
            d.name,
            COUNT(hg.id) AS house_count
        FROM skolske_obvody.house_geocodes hg
        JOIN skolske_obvody.districts d ON d.id = hg.district_id
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov' AND hg.lat IS NOT NULL
        GROUP BY d.name
        ORDER BY house_count DESC
        LIMIT 3
    """)

    print("\n" + "=" * 64)
    print("GEOCODER SUMMARY")
    print("=" * 64)
    total_calls = stats['calls']
    total_cost = total_calls * 5 / 1000
    print(f"This run: calls={total_calls}, OK={stats['ok']}, ZERO={stats['zero']}, partial={stats['partial']}, error={stats['error']}")
    print(f"Estimated cost this run: ${total_cost:.2f} USD")

    print("\nDB totals:")
    total_ok = 0
    for row in final_stats:
        print(f"  {row['status']}: {row['cnt']} (partial: {row.get('partial_cnt', 0)})")
        if row['status'] == 'OK':
            total_ok = int(row['cnt'])

    print(f"\nTop 3 districts by house points:")
    for i, row in enumerate(top_districts, 1):
        print(f"  {i}. {row['name']}: {row['house_count']} houses")

    print(f"\nFinished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
