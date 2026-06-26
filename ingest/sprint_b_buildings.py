"""
Sprint B — Replace coarse OSM-street-buffer-hull district geometry with
tighter polygons built from OSM BUILDING POLYGONS that have addr tags
matching each district's VZN street list.

Algorithm per district:
  1. Normalize district street names (strip diacritics, lower, remove "č." etc.)
  2. Collect all OSM buildings (polygon centroids) in Prešov bbox where
     addr:street matches a district street name.
  3. If qualifier (number range / odd/even) present → filter by housenumber.
  4. Build concave hull of centroids, buffer 15 m, cast to MultiPolygon.
  5. Fall back to convex hull if concave hull fails.
  6. Fall back to keeping original street-buffer hull if zero buildings matched.

Post:
  - T1 / T2 / T3 topology checks (before + after).
  - Link 2 unlinked districts via Google Places (New) API.
  - Re-run OSRM walking-distance demo.

Run:
    export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... GOOGLE_API_KEY=...
    cd projects/skolske-obvody-44
    python3 -m ingest.sprint_b_buildings
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
import uuid
from datetime import date
from typing import Optional

import requests

from ingest.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from ingest.supabase_client import exec_sql, query_sql

OSRM_URL = "http://osrm-sk:5000"
OSM_PBF_PATH = "/host-opt/frantiska-2/osrm-sk/slovakia-latest.osm.pbf"
# Prešov municipality bbox (WGS-84: lon_min, lat_min, lon_max, lat_max)
PRESOV_BBOX = (21.156965, 48.945021, 21.335406, 49.046839)
TODAY = date.today().isoformat()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY", ""))

BLOCKER_LOG: list[dict] = []
SUMMARY: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section(title: str) -> None:
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print("=" * 64)


def _blocker(source: str, reason: str) -> None:
    BLOCKER_LOG.append({"source": source, "reason": reason})
    print(f"  BLOCKER [{source}]: {reason}", file=sys.stderr)


def _strip_diacritics(text: str) -> str:
    """Decompose unicode, keep ASCII letters/digits/spaces/hyphens."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_street(name: str) -> str:
    """Lowercase, strip diacritics, remove noise tokens, collapse spaces."""
    name = name.strip()
    # Remove trailing qualifiers like "č. 29", "č.29", "ul."
    name = re.sub(r"\bč\.?\s*\d+\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\bul\.\b", "", name, flags=re.IGNORECASE)
    name = _strip_diacritics(name)
    name = name.lower()
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# Number-range qualifier parsing
# ---------------------------------------------------------------------------

def _parse_housenumber(raw: str) -> Optional[int]:
    """Extract integer from addr:housenumber like '12', '12A', '12/3'."""
    m = re.match(r"(\d+)", raw.strip())
    return int(m.group(1)) if m else None


def _qualifier_matches(housenumber_raw: str, qualifier: str) -> bool:
    """
    Return True if housenumber satisfies the qualifier string.
    Examples of qualifier strings:
      'nepárne čísla'       → odd numbers
      'párne čísla'         → even numbers
      '27 – 29'             → 27 ≤ n ≤ 29
      'párne čísla od 2 – 160'
      'číslo 6, číslo 12'   → exactly 6 or 12
      'čísla 4 – 5'         → 4 ≤ n ≤ 5
      'nepárne č. 93 – 101, 105 – 117, 119, párne č. 62 – 72'
    Falls back to True (accept) if parsing is ambiguous.
    """
    if not qualifier:
        return True
    n = _parse_housenumber(housenumber_raw)
    if n is None:
        return True  # can't determine → accept

    q_low = qualifier.lower()

    # Detect odd / even parity constraints
    odd_flag = "nepárn" in q_low or "odd" in q_low
    even_flag = ("párn" in q_low and "nepárn" not in q_low) or "even" in q_low

    # Extract all numeric ranges: "N – M" or "N-M" or single "N"
    ranges = re.findall(r"(\d+)\s*[–\-]\s*(\d+)", qualifier)
    singles = re.findall(r"číslo\s+(\d+)", q_low)

    # Build a list of (lo, hi, parity_override) segments
    # Strategy: split on comma, parse each chunk separately
    def _check_chunk(chunk: str, num: int) -> Optional[bool]:
        """Return True/False if chunk decisively passes/fails, None if no info."""
        chunk_low = chunk.lower()
        chunk_odd = "nepárn" in chunk_low
        chunk_even = ("párn" in chunk_low and "nepárn" not in chunk_low)
        rng = re.findall(r"(\d+)\s*[–\-]\s*(\d+)", chunk)
        sngl = re.findall(r"číslo\s+(\d+)", chunk_low) + re.findall(r"č\.\s*(\d+)", chunk_low)
        # If there are range/single constraints
        if rng:
            lo, hi = int(rng[0][0]), int(rng[0][1])
            in_range = lo <= num <= hi
            if not in_range:
                return False
            if chunk_odd and num % 2 == 0:
                return False
            if chunk_even and num % 2 == 1:
                return False
            return True
        if sngl:
            return num in [int(s) for s in sngl]
        # Parity only, no range
        if chunk_odd:
            return num % 2 == 1
        if chunk_even:
            return num % 2 == 0
        return None

    # Try comma-split first
    chunks = [c.strip() for c in qualifier.split(",")]
    results = [_check_chunk(c, n) for c in chunks]
    # If ANY chunk returns True → accept (building belongs to at least one sub-qualifier)
    if any(r is True for r in results):
        return True
    # If all chunks returned False → reject
    if all(r is False for r in results):
        return False

    # Fallback: global parity check without ranges
    if odd_flag and not ranges and not singles:
        return n % 2 == 1
    if even_flag and not ranges and not singles:
        return n % 2 == 0

    return True  # ambiguous → accept


# ---------------------------------------------------------------------------
# Step 1 — Parse buildings from OSM PBF
# ---------------------------------------------------------------------------

def extract_presov_buildings(pbf_path: str, bbox: tuple) -> list[dict]:
    """
    Parse OSM PBF for buildings with addr:street within Prešov bbox.
    Returns list of dicts:
      {street_norm, street_raw, housenumber, lon, lat}
    where lon/lat is the building centroid.
    """
    import osmium

    minx, miny, maxx, maxy = bbox

    # We need node locations for way coordinate resolution
    buildings: list[dict] = []

    class BuildingHandler(osmium.SimpleHandler):
        def _in_bbox(self, coords: list) -> bool:
            if not coords:
                return False
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            return (max(lons) >= minx and min(lons) <= maxx and
                    max(lats) >= miny and min(lats) <= maxy)

        def _centroid(self, coords: list) -> tuple:
            lon = sum(c[0] for c in coords) / len(coords)
            lat = sum(c[1] for c in coords) / len(coords)
            return lon, lat

        def _emit(self, tags: dict, coords: list) -> None:
            if not tags.get("building"):
                return
            street = tags.get("addr:street", "").strip()
            if not street:
                return
            if not coords or not self._in_bbox(coords):
                return
            lon, lat = self._centroid(coords)
            hn = tags.get("addr:housenumber", "").strip()
            buildings.append({
                "street_raw": street,
                "street_norm": _normalize_street(street),
                "housenumber": hn,
                "lon": lon,
                "lat": lat,
            })

        def node(self, n):
            tags = {t.k: t.v for t in n.tags}
            if not tags.get("building") or not tags.get("addr:street"):
                return
            lon, lat = n.location.lon, n.location.lat
            if not (minx <= lon <= maxx and miny <= lat <= maxy):
                return
            street = tags.get("addr:street", "").strip()
            hn = tags.get("addr:housenumber", "").strip()
            buildings.append({
                "street_raw": street,
                "street_norm": _normalize_street(street),
                "housenumber": hn,
                "lon": lon,
                "lat": lat,
            })

        def way(self, w):
            tags = {t.k: t.v for t in w.tags}
            if not tags.get("building") or not tags.get("addr:street"):
                return
            try:
                coords = [(nd.lon, nd.lat) for nd in w.nodes]
            except osmium.InvalidLocationError:
                return
            self._emit(tags, coords)

        def relation(self, r):
            # Skip relations for now (multipolygon buildings are rare with addr tags)
            pass

    handler = BuildingHandler()
    print(f"  Parsing OSM PBF for buildings with addr:street ...")
    handler.apply_file(pbf_path, locations=True)
    print(f"  Extracted {len(buildings)} building addr-points in Prešov bbox")
    return buildings


# ---------------------------------------------------------------------------
# Step 2 — Build geometry for one district
# ---------------------------------------------------------------------------

def build_district_geom_from_buildings(
    streets: list[str],
    qualifiers: dict,
    buildings: list[dict],
) -> tuple[Optional[str], int, list[str]]:
    """
    Match buildings to district streets, build concave hull.
    Returns: (ewkt_multipolygon | None, matched_count, unmatched_streets)
    """
    from shapely import concave_hull, convex_hull
    from shapely.geometry import MultiPoint, MultiPolygon, Point
    from shapely.ops import unary_union
    from shapely.wkt import dumps as wkt_dumps

    # Normalize district street names
    norm_streets: dict[str, tuple[str, str]] = {}  # norm → (raw_name, qualifier)
    for sname in streets:
        norm = _normalize_street(sname)
        qual = qualifiers.get(sname, "")
        norm_streets[norm] = (sname, qual)

    # Collect matching building centroids
    matched_points: list[Point] = []
    matched_street_set: set[str] = set()

    for b in buildings:
        bn = b["street_norm"]
        if bn not in norm_streets:
            continue
        raw_name, qual = norm_streets[bn]
        if qual:
            hn = b.get("housenumber", "")
            if not _qualifier_matches(hn, qual):
                continue
        matched_points.append(Point(b["lon"], b["lat"]))
        matched_street_set.add(raw_name)

    unmatched = [s for s in streets if s not in matched_street_set]

    if len(matched_points) < 3:
        return None, len(matched_points), unmatched

    mp = MultiPoint(matched_points)

    # Try concave hull first (shapely 2.x top-level function)
    try:
        hull = concave_hull(mp, ratio=0.3)
        if hull.is_empty or hull.area == 0:
            raise ValueError("empty concave hull")
    except Exception:
        hull = convex_hull(mp)

    if hull.is_empty or hull.area == 0:
        return None, len(matched_points), unmatched

    # Buffer ~15 m (≈ 0.000135° latitude)
    buffered = hull.buffer(0.000135)

    # Ensure MultiPolygon
    if buffered.geom_type == "Polygon":
        buffered = MultiPolygon([buffered])
    elif buffered.geom_type == "GeometryCollection":
        polys = [g for g in buffered.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        if polys:
            buffered = unary_union(polys)
            if buffered.geom_type == "Polygon":
                buffered = MultiPolygon([buffered])
        else:
            return None, len(matched_points), unmatched

    if buffered.is_empty:
        return None, len(matched_points), unmatched

    wkt = wkt_dumps(buffered, rounding_precision=7)
    ewkt = f"SRID=4326;{wkt}" if wkt.upper().startswith("MULTIPOLYGON") else f"SRID=4326;MULTIPOLYGON(({wkt[wkt.index('('):]}))"
    # Make sure EWKT is proper
    if "MULTIPOLYGON" not in ewkt.upper():
        ewkt = f"SRID=4326;{wkt}"
    return ewkt, len(matched_points), unmatched


# ---------------------------------------------------------------------------
# Step 3 — Update all districts
# ---------------------------------------------------------------------------

def update_district_geometries(buildings: list[dict]) -> dict:
    """
    For each district in DB, attempt building-based geometry.
    Falls back to existing geom if zero buildings match.
    Returns summary dict.
    """
    _section("UPDATE DISTRICT GEOMETRIES — buildings addr concave hull")

    districts = query_sql("""
SELECT id, name, school_id, geometry_quality, metadata
FROM skolske_obvody.districts
ORDER BY name
""")

    updated = 0
    kept_fallback = 0
    too_few_buildings = 0

    per_district = []

    for d in districts:
        district_id = d["id"]
        name = d["name"]
        meta = d.get("metadata") or {}
        streets = meta.get("streets", [])
        qualifiers = meta.get("street_qualifiers", {})
        if not streets:
            print(f"  SKIP [{name[:45]}]: no streets in metadata")
            kept_fallback += 1
            per_district.append({"name": name, "streets": 0, "matched_buildings": 0, "outcome": "NO_STREETS"})
            continue

        ewkt, matched_n, unmatched = build_district_geom_from_buildings(streets, qualifiers, buildings)

        if ewkt is None:
            msg = f"< 3 buildings matched ({matched_n})" if matched_n > 0 else "0 buildings matched"
            print(f"  FALLBACK [{name[:45]}]: {msg} — keeping street-buffer hull")
            kept_fallback += 1
            too_few_buildings += (1 if matched_n < 3 else 0)
            per_district.append({
                "name": name,
                "streets": len(streets),
                "matched_buildings": matched_n,
                "outcome": "KEPT_FALLBACK",
                "unmatched_streets": len(unmatched),
            })
            continue

        # Update metadata
        meta["geom_method"] = "osm_buildings_addr_concave_hull"
        meta["geom_input_buildings"] = matched_n
        meta["unresolved_streets"] = unmatched if unmatched else []
        meta_json = json.dumps(meta, ensure_ascii=False)

        sql = f"""
UPDATE skolske_obvody.districts
SET
    geom = public.ST_GeomFromEWKT($_geom${ewkt}$_geom$),
    geometry_quality = 7,
    geometry_confidence = 'medium',
    metadata = $_meta${meta_json}$_meta$::jsonb
WHERE id = '{district_id}'
"""
        r = exec_sql(sql)
        if r.get("ok"):
            print(f"  OK [{name[:45]}]: {matched_n} buildings matched, {len(unmatched)} streets unresolved")
            updated += 1
            per_district.append({
                "name": name,
                "streets": len(streets),
                "matched_buildings": matched_n,
                "unresolved_streets": len(unmatched),
                "outcome": "UPDATED",
            })
        else:
            err = r.get("message", "?")
            print(f"  ERROR [{name[:45]}]: {err}", file=sys.stderr)
            kept_fallback += 1
            per_district.append({
                "name": name,
                "streets": len(streets),
                "matched_buildings": matched_n,
                "outcome": f"DB_ERROR: {err[:60]}",
            })

    summary = {
        "updated_quality7": updated,
        "kept_fallback": kept_fallback,
        "total": len(districts),
    }
    print(f"\n  Updated to quality=7: {updated}/{len(districts)}")
    print(f"  Kept fallback (street-buffer): {kept_fallback}/{len(districts)}")

    return {"summary": summary, "per_district": per_district}


# ---------------------------------------------------------------------------
# Topology checks
# ---------------------------------------------------------------------------

def topology_checks(label: str = "") -> dict:
    _section(f"TOPOLOGY CHECKS {label}")

    # T1
    print("\nT1 — ST_IsValid:")
    rows = query_sql("""
SELECT name,
       public.ST_IsValid(geom) as valid,
       geom IS NOT NULL as has_geom
FROM skolske_obvody.districts
ORDER BY name
""")
    valid_n = sum(1 for r in rows if r.get("valid"))
    geom_n = sum(1 for r in rows if r.get("has_geom"))
    for r in rows:
        status = "VALID" if r.get("valid") else ("NULL_GEOM" if not r.get("has_geom") else "INVALID")
        print(f"  [{status}] {r['name'][:55]}")
    print(f"  → {geom_n} with geom, {valid_n}/12 pass ST_IsValid")

    # T2: overlaps within same type+language
    print("\nT2 — District overlaps (same school type + language):")
    rows2 = query_sql("""
SELECT COUNT(*) AS n
FROM skolske_obvody.districts a
JOIN skolske_obvody.districts b ON a.id < b.id
JOIN skolske_obvody.schools sa ON sa.id = a.school_id
JOIN skolske_obvody.schools sb ON sb.id = b.school_id
WHERE sa.type = sb.type
  AND sa.teaching_language = sb.teaching_language
  AND a.geom IS NOT NULL AND b.geom IS NOT NULL
  AND public.ST_Intersects(a.geom, b.geom)
  AND public.ST_Area(public.ST_Intersection(a.geom, b.geom)) > 0.000001
""")
    t2_school_linked = int(rows2[0]["n"]) if rows2 else -1

    rows3 = query_sql("""
SELECT COUNT(*) AS n
FROM skolske_obvody.districts a
JOIN skolske_obvody.districts b ON a.id < b.id
WHERE a.geom IS NOT NULL AND b.geom IS NOT NULL
  AND public.ST_Intersects(a.geom, b.geom)
  AND public.ST_Area(public.ST_Intersection(a.geom, b.geom)) > 0.000001
""")
    t2_all = int(rows3[0]["n"]) if rows3 else -1
    print(f"  T2 overlap pairs (school-linked same type+lang): {t2_school_linked}")
    print(f"  T2 overlap pairs (all districts): {t2_all}")

    # T3: school within / near polygon
    print("\nT3 — School position in/near polygon:")
    rows4 = query_sql("""
SELECT
    d.name AS district_name,
    d.geom IS NOT NULL AS has_geom,
    d.school_id IS NOT NULL AS has_school_fk,
    public.ST_Contains(d.geom, s.geom) AS school_inside,
    public.ST_Distance(
        d.geom::public.geography,
        s.geom::public.geography
    ) AS dist_m
FROM skolske_obvody.districts d
LEFT JOIN skolske_obvody.schools s ON s.id = d.school_id
ORDER BY d.name
""")
    t3_inside = 0
    t3_within50 = 0
    for r in rows4:
        if not r.get("has_school_fk"):
            status = "NO_FK"
        elif not r.get("has_geom"):
            status = "NO_GEOM"
        elif r.get("school_inside"):
            status = "INSIDE"
            t3_inside += 1
            t3_within50 += 1
        else:
            dist = r.get("dist_m") or 9999
            if dist <= 50:
                status = f"WITHIN_50m ({dist:.0f}m)"
                t3_within50 += 1
            else:
                status = f"FAR {dist:.0f}m"
        print(f"  [{status}] {r['district_name'][:55]}")
    fk_total = sum(1 for r in rows4 if r.get("has_school_fk"))
    print(f"  → School inside polygon: {t3_inside}/{fk_total} linked")
    print(f"  → School inside or within 50m: {t3_within50}/{fk_total} linked")

    return {
        "T1_valid": valid_n,
        "T1_geom": geom_n,
        "T2_pairs_school_linked": t2_school_linked,
        "T2_pairs_all": t2_all,
        "T3_inside": t3_inside,
        "T3_within50": t3_within50,
    }


# ---------------------------------------------------------------------------
# Step 6 — Link 2 unlinked districts via Google Places (New)
# ---------------------------------------------------------------------------

UNLINKED_DISTRICTS = [
    {
        "district_name": "Základná škola, Prostějovská č. 38",
        "places_query": "Základná škola Prostějovská 38 Prešov",
        "city": "Prešov",
    },
    {
        "district_name": "Základná škola, Šrobárova č. 20",
        "places_query": "Základná škola Šrobárova 20 Prešov",
        "city": "Prešov",
    },
]


def _google_places_text_search(query: str, api_key: str) -> Optional[dict]:
    """
    Call Google Places (New) Text Search API.
    Returns dict with name, lat, lon, place_id or None on failure.
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.location,places.id,places.formattedAddress",
    }
    payload = {
        "textQuery": query,
        "languageCode": "sk",
        "locationBias": {
            "circle": {
                "center": {"latitude": 48.996, "longitude": 21.239},
                "radius": 10000.0,
            }
        },
        "maxResultCount": 3,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        data = resp.json()
        places = data.get("places", [])
        if not places:
            return None
        p = places[0]
        loc = p.get("location", {})
        return {
            "name": p.get("displayName", {}).get("text", ""),
            "lat": loc.get("latitude"),
            "lon": loc.get("longitude"),
            "place_id": p.get("id", ""),
            "address": p.get("formattedAddress", ""),
        }
    except Exception as e:
        print(f"  Google Places error: {e}", file=sys.stderr)
        return None


def link_unlinked_districts() -> dict:
    _section("LINK 2 UNLINKED DISTRICTS via Google Places")

    if not GOOGLE_API_KEY:
        _blocker("link_unlinked", "GOOGLE_API_KEY not set — skipping Places lookup")
        return {"linked": 0, "details": []}

    results = []

    for item in UNLINKED_DISTRICTS:
        district_name = item["district_name"]
        query = item["places_query"]

        print(f"\n  Searching: {query}")
        place = _google_places_text_search(query, GOOGLE_API_KEY)

        if not place:
            print(f"  → No Google Places result")
            results.append({"district": district_name, "outcome": "NO_PLACES_RESULT"})
            continue

        print(f"  → Found: {place['name']} @ {place['lat']:.5f},{place['lon']:.5f}")
        print(f"     Address: {place['address']}")
        lon, lat = place["lon"], place["lat"]

        # Check if school exists in DB within 300m
        nearby = query_sql(f"""
SELECT id, name,
       public.ST_Distance(
           public.ST_SetSRID(public.ST_MakePoint({lon}, {lat}), 4326)::public.geography,
           geom::public.geography
       ) AS dist_m
FROM skolske_obvody.schools
WHERE public.ST_DWithin(
    public.ST_SetSRID(public.ST_MakePoint({lon}, {lat}), 4326)::public.geography,
    geom::public.geography,
    500
)
ORDER BY dist_m
LIMIT 1
""")

        if nearby:
            school_id = nearby[0]["id"]
            school_name = nearby[0]["name"]
            dist_m = nearby[0]["dist_m"]
            print(f"  → Matched existing school: {school_name} ({dist_m:.0f}m away)")
            outcome = f"LINKED_EXISTING (dist={dist_m:.0f}m)"
        else:
            # Insert new school record
            school_id = str(uuid.uuid4())
            new_school_name = place["name"] or district_name
            geom_ewkt = f"SRID=4326;POINT({lon} {lat})"
            prov = json.dumps({
                "source": "google_places_new",
                "place_id": place["place_id"],
                "address": place["address"],
                "fetched_at": TODAY,
            })
            ins_sql = f"""
INSERT INTO skolske_obvody.schools
    (id, name, type, is_public, teaching_language, geom, source_name, source_date, municipality_id)
VALUES (
    '{school_id}',
    $_name${new_school_name}$_name$,
    'ZS',
    TRUE,
    'SK',
    public.ST_GeomFromEWKT($_geom${geom_ewkt}$_geom$),
    'google_places_new',
    '{TODAY}',
    'e74cc008-e6e3-4b4d-abae-0c62d240ba01'
)
ON CONFLICT (id) DO NOTHING
"""
            r = exec_sql(ins_sql)
            if r.get("ok"):
                print(f"  → Inserted new school: {new_school_name}")
                outcome = "INSERTED_NEW_SCHOOL"
            else:
                print(f"  → INSERT failed: {r.get('message', '?')}", file=sys.stderr)
                outcome = f"INSERT_FAILED: {r.get('message','?')[:60]}"
                results.append({"district": district_name, "outcome": outcome, "place": place})
                continue

        # Find district by name and update school_id
        dist_rows = query_sql(f"""
SELECT id FROM skolske_obvody.districts
WHERE name = $_n${district_name}$_n$
LIMIT 1
""")
        if not dist_rows:
            print(f"  → District not found in DB: {district_name}", file=sys.stderr)
            results.append({"district": district_name, "outcome": "DISTRICT_NOT_FOUND", "place": place})
            continue

        dist_id = dist_rows[0]["id"]
        upd_sql = f"""
UPDATE skolske_obvody.districts
SET school_id = '{school_id}',
    metadata = jsonb_set(
        COALESCE(metadata, '{{}}'),
        '{{school_geocoded_lat}}',
        '{lat}'::jsonb
    ) ||
    jsonb_build_object(
        'school_geocoded_lat', {lat},
        'school_geocoded_lon', {lon},
        'school_places_name', $_pn${place['name']}$_pn$,
        'school_places_address', $_pa${place['address']}$_pa$
    )
WHERE id = '{dist_id}'
"""
        r2 = exec_sql(upd_sql)
        if r2.get("ok"):
            print(f"  → Updated district FK → school_id={school_id}")
        else:
            print(f"  → District FK update failed: {r2.get('message','?')}", file=sys.stderr)

        results.append({
            "district": district_name,
            "places_name": place["name"],
            "places_address": place["address"],
            "outcome": outcome,
            "lat": lat,
            "lon": lon,
        })

    linked_count = sum(1 for r in results if "LINKED" in r.get("outcome", "") or "INSERTED" in r.get("outcome", ""))
    return {"linked": linked_count, "details": results}


# ---------------------------------------------------------------------------
# Walking distance demo
# ---------------------------------------------------------------------------

def osrm_walking_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> Optional[float]:
    url = f"{OSRM_URL}/route/v1/walking/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("code") == "Ok":
            return data["routes"][0]["distance"]
    except Exception as e:
        print(f"  OSRM error: {e}", file=sys.stderr)
    return None


def walking_distance_demo() -> dict:
    _section("WALKING DISTANCE DEMO — district centroid → school (OSRM)")

    rows = query_sql("""
SELECT
    d.name AS district_name,
    d.school_type,
    public.ST_X(public.ST_Centroid(d.geom)) AS d_lon,
    public.ST_Y(public.ST_Centroid(d.geom)) AS d_lat,
    COALESCE(
        (d.metadata->>'school_geocoded_lon')::float,
        public.ST_X(s.geom)
    ) AS s_lon,
    COALESCE(
        (d.metadata->>'school_geocoded_lat')::float,
        public.ST_Y(s.geom)
    ) AS s_lat
FROM skolske_obvody.districts d
LEFT JOIN skolske_obvody.schools s ON s.id = d.school_id
WHERE d.geom IS NOT NULL
  AND (
    d.metadata->>'school_geocoded_lon' IS NOT NULL
    OR s.geom IS NOT NULL
  )
ORDER BY d.name
""")

    if not rows:
        _blocker("walking_demo", "No districts with geom + school position")
        return {}

    print(f"\n  {'District':<47} {'Type':<4} {'Dist_m':>7} {'Thresh':>7} {'Status':>6}")
    print(f"  {'-'*47} {'-'*4} {'-'*7} {'-'*7} {'-'*6}")

    demo_rows = []
    pass_n = risk_n = fail_n = osrm_fail_n = 0

    for r in rows:
        d_lon, d_lat = r["d_lon"], r["d_lat"]
        s_lon, s_lat = r["s_lon"], r["s_lat"]
        if d_lon is None or s_lon is None:
            continue

        dist = osrm_walking_distance(d_lon, d_lat, s_lon, s_lat)
        stype = r.get("school_type") or "ZS"
        threshold = 4000 if stype == "MS" else 2000

        if dist is None:
            status = "OSRM_FAIL"
            osrm_fail_n += 1
        elif dist <= threshold:
            status = "PASS"
            pass_n += 1
        elif dist <= threshold * 1.25:
            status = "RISK"
            risk_n += 1
        else:
            status = "FAIL"
            fail_n += 1

        dist_str = f"{dist:.0f}" if dist is not None else "ERR"
        print(f"  {r['district_name'][:47]:<47} {stype:<4} {dist_str:>7} {threshold:>7} {status:>6}")
        demo_rows.append({"name": r["district_name"], "dist_m": dist, "status": status})

    print(f"\n  PASS: {pass_n} | RISK: {risk_n} | FAIL: {fail_n} | OSRM_FAIL: {osrm_fail_n}")
    return {"pass": pass_n, "risk": risk_n, "fail": fail_n, "osrm_fail": osrm_fail_n, "rows": demo_rows}


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> int:
    print("Sprint B — OSM Building addr-based district geometry")
    print(f"Target: {SUPABASE_URL[:55]}")
    print(f"PBF: {OSM_PBF_PATH}")
    print(f"Google API key: {'SET' if GOOGLE_API_KEY else 'NOT SET'}")

    # T2 BEFORE
    _section("T2 BASELINE (before update)")
    rows_before = query_sql("""
SELECT COUNT(*) AS n
FROM skolske_obvody.districts a
JOIN skolske_obvody.districts b ON a.id < b.id
JOIN skolske_obvody.schools sa ON sa.id = a.school_id
JOIN skolske_obvody.schools sb ON sb.id = b.school_id
WHERE sa.type = sb.type
  AND sa.teaching_language = sb.teaching_language
  AND a.geom IS NOT NULL AND b.geom IS NOT NULL
  AND public.ST_Intersects(a.geom, b.geom)
  AND public.ST_Area(public.ST_Intersection(a.geom, b.geom)) > 0.000001
""")
    t2_before = int(rows_before[0]["n"]) if rows_before else -1
    print(f"  T2 before: {t2_before} overlap pairs (school-linked)")
    SUMMARY["T2_before"] = t2_before

    # Step 1 — extract buildings
    _section("STEP 1: Extract buildings from OSM PBF")
    buildings = extract_presov_buildings(OSM_PBF_PATH, PRESOV_BBOX)
    if not buildings:
        _blocker("osm_buildings", "Zero buildings extracted from PBF")
        return 1
    SUMMARY["total_buildings_extracted"] = len(buildings)

    # Step 2+3 — build and update district geometries
    geo_result = update_district_geometries(buildings)
    SUMMARY.update(geo_result["summary"])
    SUMMARY["per_district"] = geo_result["per_district"]

    # T1/T2/T3 AFTER
    topo = topology_checks("AFTER UPDATE")
    SUMMARY.update(topo)

    # Step 6 — link 2 unlinked districts
    link_result = link_unlinked_districts()
    SUMMARY["places_linked"] = link_result["linked"]
    SUMMARY["places_details"] = link_result["details"]

    # Walking demo
    walk = walking_distance_demo()
    SUMMARY["walking_demo"] = walk

    # Final report
    _section("FINAL SUMMARY")
    print(f"\n  Buildings extracted from OSM: {SUMMARY['total_buildings_extracted']}")
    print(f"\n  Districts updated (quality=7): {SUMMARY.get('updated_quality7', '?')}")
    print(f"  Districts kept fallback:       {SUMMARY.get('kept_fallback', '?')}")
    print(f"\n  T2 overlap pairs BEFORE: {SUMMARY.get('T2_before', '?')} (school-linked)")
    print(f"  T2 overlap pairs AFTER:  {SUMMARY.get('T2_pairs_school_linked', '?')} (school-linked)")
    print(f"  T2 all-pairs AFTER:      {SUMMARY.get('T2_pairs_all', '?')}")
    print(f"\n  T1 valid geometries:     {SUMMARY.get('T1_valid', '?')}/12")
    print(f"\n  Walking demo: {walk.get('pass','?')} PASS / {walk.get('risk','?')} RISK / {walk.get('fail','?')} FAIL")

    print("\n  Per-district breakdown:")
    print(f"  {'District':<47} {'Streets':>7} {'Bldgs':>6} {'Outcome'}")
    print(f"  {'-'*47} {'-'*7} {'-'*6} {'-'*20}")
    for pd in SUMMARY.get("per_district", []):
        print(
            f"  {pd['name'][:47]:<47} "
            f"{pd.get('streets', 0):>7} "
            f"{pd.get('matched_buildings', 0):>6} "
            f"{pd.get('outcome', '?')}"
        )

    print("\n  Places API results:")
    for pr in SUMMARY.get("places_details", []):
        print(f"    {pr['district'][:45]}: {pr.get('outcome','?')}")
        if pr.get("places_name"):
            print(f"      → {pr['places_name']} @ {pr.get('places_address','')}")

    if BLOCKER_LOG:
        print("\nBLOCKERS:")
        for b in BLOCKER_LOG:
            print(f"  [{b['source']}] {b['reason']}")

    return 1 if BLOCKER_LOG else 0


if __name__ == "__main__":
    sys.exit(main())
