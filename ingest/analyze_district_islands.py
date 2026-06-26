"""
Sprint L — Analyze disconnected Voronoi islands per district.

For each Prešov district:
  1. Decompose geom_voronoi into individual polygon parts (ST_Dump)
  2. Per island: area in m² (ST_Area with SRID 5514 / Krovak), streets, house numbers
  3. Insert into district_islands table
  4. Per-district report: island count, biggest/smallest, top 3 with streets

Also performs a WebFetch check on ZŠ Šmeralova č. 25 for language/minority
specialization. Logs result to metadata (no HTTP library needed, pure urllib).

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /'))
    python3 ingest/analyze_district_islands.py
"""

from __future__ import annotations

import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SMERALOVA_ID = "cddfee4e-fb1d-48c1-bbb5-2626ae415f87"
SMERALOVA_WEB_URLS = [
    "https://zsmeralova.edupage.org/",
    "https://www.zsmeralova.sk/",
    "https://www.presov.sk/skoly/zakladne-skoly/zs-smeralova-25.html",
]
SPECIALTY_KEYWORDS = [
    "rómsky", "romský", "menšina", "jazyk", "špecializácia",
    "bilingválne", "cudzí jazyk", "special", "minority", "language",
    "špeciálna", "dvojjazyčné", "anglický", "nemecký",
]


# ---------------------------------------------------------------------------
# WebFetch check for Šmeralova
# ---------------------------------------------------------------------------

def _fetch_text(url: str, timeout: int = 10) -> str | None:
    """Fetch URL body as text. Returns None on any error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WebFetch {url}: {e}")
        return None


def check_smeralova_specialty() -> dict:
    """
    Check ZŠ Šmeralova webpages for language/minority specialization.
    Returns {'found': bool, 'url': str|None, 'snippet': str|None}
    """
    print("\n[Šmeralova web check]")
    for url in SMERALOVA_WEB_URLS:
        text = _fetch_text(url)
        if text is None:
            print(f"  SKIP: {url} — fetch failed")
            continue
        text_lower = text.lower()
        for kw in SPECIALTY_KEYWORDS:
            if kw.lower() in text_lower:
                # Find surrounding snippet
                idx = text_lower.find(kw.lower())
                snippet = text[max(0, idx - 60): idx + 100].replace("\n", " ").strip()
                print(f"  FOUND keyword '{kw}' at {url}")
                print(f"  Snippet: ...{snippet}...")
                return {"found": True, "url": url, "keyword": kw, "snippet": snippet}
        print(f"  No specialty keywords found at {url}")

    print("  Result: no specialty info found on any checked URL")
    return {
        "found": False,
        "url": None,
        "keyword": None,
        "snippet": None,
        "checked_urls": SMERALOVA_WEB_URLS,
    }


# ---------------------------------------------------------------------------
# Populate district_islands table
# ---------------------------------------------------------------------------

POPULATE_SQL = """
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
),
dumped AS (
  SELECT
    d.id AS district_id,
    (public.ST_Dump(d.geom_voronoi)).path[1] - 1 AS island_index,
    (public.ST_Dump(d.geom_voronoi)).geom        AS island_geom
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = (SELECT id FROM presov)
    AND d.geom_voronoi IS NOT NULL
),
with_stats AS (
  SELECT
    du.district_id,
    du.island_index,
    round(public.ST_Area(public.ST_Transform(du.island_geom, 5514))::numeric, 1) AS area_m2,
    du.island_geom AS geom,
    array_remove(array_agg(DISTINCT hg.street ORDER BY hg.street), NULL) AS streets,
    array_remove(array_agg(DISTINCT hg.house_number ORDER BY hg.house_number), NULL) AS house_numbers
  FROM dumped du
  LEFT JOIN skolske_obvody.house_geocodes hg
    ON hg.district_id = du.district_id
    AND hg.valid = true
    AND hg.geom IS NOT NULL
    AND public.ST_Contains(du.island_geom, hg.geom)
  GROUP BY du.district_id, du.island_index, du.island_geom
)
INSERT INTO skolske_obvody.district_islands
  (district_id, island_index, area_m2, geom, streets, house_numbers)
SELECT district_id, island_index, area_m2, geom, streets, house_numbers
FROM with_stats
ON CONFLICT (district_id, island_index) DO UPDATE SET
  area_m2       = EXCLUDED.area_m2,
  geom          = EXCLUDED.geom,
  streets       = EXCLUDED.streets,
  house_numbers = EXCLUDED.house_numbers
"""


def populate_islands() -> None:
    print("\n[A] Populating district_islands table...")
    r = exec_sql(POPULATE_SQL)
    if not r.get("ok"):
        raise RuntimeError(f"populate_islands failed: {r.get('message')}")
    print("  Populated OK")


# ---------------------------------------------------------------------------
# Per-district island report
# ---------------------------------------------------------------------------

def island_report() -> list[dict]:
    """Return per-district island stats."""
    rows = query_sql("""
        SELECT
          d.id,
          d.name,
          COUNT(di.island_index)         AS island_count,
          MAX(di.area_m2)                AS biggest_area_m2,
          MIN(di.area_m2)                AS smallest_area_m2,
          SUM(di.area_m2)                AS total_area_m2
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.district_islands di ON di.district_id = d.id
        WHERE d.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
        GROUP BY d.id, d.name
        ORDER BY COUNT(di.island_index) DESC, d.name
    """)
    return rows


def top3_islands(district_id: str) -> list[dict]:
    """Return top 3 islands for a district, sorted by area desc."""
    return query_sql(f"""
        SELECT island_index, area_m2, streets, house_numbers
        FROM skolske_obvody.district_islands
        WHERE district_id = $__did_${district_id}$__did_$
        ORDER BY area_m2 DESC
        LIMIT 3
    """.replace("$__did_$", "$_did_$"))


def smeralova_islands() -> list[dict]:
    """Return all islands for Šmeralova, ordered by island_index."""
    return query_sql(f"""
        SELECT island_index, area_m2, streets, house_numbers,
               array_length(streets, 1) AS street_count,
               array_length(house_numbers, 1) AS house_count
        FROM skolske_obvody.district_islands
        WHERE district_id = $__sid__${SMERALOVA_ID}$__sid__$
        ORDER BY island_index
    """.replace("$__sid__$", "$_sid_$"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_config()

    print("=" * 64)
    print("Sprint L — District Island Analysis")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 64)

    # A: Šmeralova web check
    smeralova_check = check_smeralova_specialty()

    # B: Populate district_islands
    populate_islands()

    # C: Per-district report
    print("\n[B] Per-district island report:")
    stats = island_report()

    print(f"\n  {'District':<52} {'Islands':>7} {'BiggestIsland':>14} {'SmallestIsland':>14}")
    print("  " + "-" * 90)
    for r in stats:
        name = (r.get("name") or "?")[:51]
        islands = int(r.get("island_count") or 1)
        biggest = float(r.get("biggest_area_m2") or 0)
        smallest = float(r.get("smallest_area_m2") or 0)
        flag = " ⚠" if islands > 1 else ""
        print(f"  {name:<52} {islands:>7}   {biggest:>10.0f} m²  {smallest:>10.0f} m²{flag}")

    # D: Top 3 islands per district (streets)
    print("\n[C] Top 3 islands per district (by area):")
    for r in stats:
        if int(r.get("island_count") or 1) < 2:
            continue
        name = (r.get("name") or "?")
        district_id = r["id"]
        top3 = query_sql(f"""
            SELECT island_index, area_m2, streets, house_numbers,
                   array_length(streets, 1) AS street_count,
                   array_length(house_numbers, 1) AS house_count
            FROM skolske_obvody.district_islands
            WHERE district_id = $_did_${district_id}$_did_$
            ORDER BY area_m2 DESC
            LIMIT 3
        """)
        print(f"\n  {name}")
        for isl in top3:
            streets = isl.get("streets") or []
            sc = isl.get("street_count") or 0
            hc = isl.get("house_count") or 0
            area = float(isl.get("area_m2") or 0)
            streets_str = ", ".join(streets[:5])
            if len(streets) > 5:
                streets_str += f" (+{len(streets) - 5})"
            print(f"    Island {isl['island_index']}: {area:,.0f} m² | {sc} ulíc | {hc} domov | {streets_str or '—'}")

    # E: Šmeralova detailed islands
    print("\n[D] ZŠ Šmeralova č. 25 — island detail:")
    sm_islands = smeralova_islands()
    for isl in sm_islands:
        streets = isl.get("streets") or []
        hns = isl.get("house_numbers") or []
        area = float(isl.get("area_m2") or 0)
        sc = isl.get("street_count") or 0
        hc = isl.get("house_count") or 0
        print(f"  Island {isl['island_index']}: {area:,.1f} m²  {sc} ulíc  {hc} domov")
        if streets:
            print(f"    Ulice: {', '.join(streets)}")
        if hns:
            hn_sample = ", ".join(hns[:10])
            suffix = f" (+{len(hns) - 10} more)" if len(hns) > 10 else ""
            print(f"    Čísla domov: {hn_sample}{suffix}")

    # F: Šmeralova web check summary
    print("\n[E] ZŠ Šmeralova web check:")
    if smeralova_check["found"]:
        print(f"  FOUND specialty keyword: '{smeralova_check['keyword']}'")
        print(f"  URL: {smeralova_check['url']}")
        print(f"  Snippet: {smeralova_check['snippet']}")
    else:
        print(f"  No specialty info found. Checked: {', '.join(smeralova_check['checked_urls'])}")
        print("  Conclusion: Disconnected ostrovy sú bez zisteného školského dôvodu.")

    print("\n" + "=" * 64)
    print("SPRINT L SUMMARY")
    print("=" * 64)
    multi = [r for r in stats if int(r.get("island_count") or 1) > 1]
    print(f"Districts with islands: {len(multi)} / {len(stats)}")
    print(f"Šmeralova islands: {sum(1 for r in stats if r['id'] == SMERALOVA_ID and True)} sets")
    sm = next((r for r in stats if r["id"] == SMERALOVA_ID), None)
    if sm:
        print(f"  island_count={sm['island_count']}, biggest={float(sm['biggest_area_m2']):,.0f} m², smallest={float(sm['smallest_area_m2']):,.0f} m²")
    if smeralova_check["found"]:
        print(f"Šmeralova specialty: {smeralova_check['keyword']} ({smeralova_check['url']})")
    else:
        print("Šmeralova specialty: not found → flag 'bez známeho dôvodu'")
    print(f"\nFinished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
