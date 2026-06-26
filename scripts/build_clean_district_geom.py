"""
Sprint M-2 — Build clean district geometry GeoJSON.

Fallback strategy (per Sprint M PRD §M-2 mockdata fallback):
  - For 3 chosen "showcase" districts, generate a smoothed + simplified polygon
    derived from the existing Voronoi geometry (tag = 'clean_polygon').
    Stronger simplify tolerance + ST_Buffer round joins produce a polygon
    that visually reads as a street-aligned obvod rather than a Voronoi
    cell crisscrossing through individual houses.
  - For the remaining 9 districts, copy the existing Voronoi geometry with a
    light cleanup (tag = 'voronoi_fallback'), so the map still shows every
    obvod, with a banner explaining that only the 3 showcase polygons are
    hand-tuned demo data.

Output: data/clean_district_geom.geojson (FeatureCollection)
        — feature.id      = district uuid
        — feature.properties.name = district name
        — feature.properties.method = 'clean_polygon' | 'voronoi_fallback'
        — feature.properties.demo = true

The full OSM street-snap pipeline (the "real" path the PRD outlines) is a
follow-up sprint; this script makes the map honestly demonstrable today.

Usage:
  python3 scripts/build_clean_district_geom.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.supabase_client import query_sql  # noqa: E402

OUT_PATH = ROOT / "data" / "clean_district_geom.geojson"

# Three showcase districts that get the stronger smoothing + 'clean_polygon'
# label. Picked by name fragment so renames in DB do not break the script.
# These three cover three sectors of Prešov (central, north-east, south),
# giving the demo a visible variety of polygon shapes.
SHOWCASE_NAME_FRAGMENTS = [
    "Sibírska",
    "Šmeralova",
    "Bajkalská",
]


def fetch_districts() -> list[dict]:
    """Pull Prešov districts with their Voronoi geometry as GeoJSON."""
    rows = query_sql(
        """
        SELECT
          d.id::text AS id,
          d.name,
          public.ST_AsGeoJSON(
            public.ST_Multi(
              public.ST_CollectionExtract(
                public.ST_MakeValid(d.geom_voronoi),
                3
              )
            )
          )::text AS voronoi_geojson
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
          AND d.geom_voronoi IS NOT NULL
        ORDER BY d.name
        """
    )
    return rows


def smooth_polygon_sql(district_id: str, strong: bool) -> str:
    """
    Build a SQL expression that returns a smoothed MultiPolygon GeoJSON for
    one district. We do this server-side so we don't need shapely on the
    host — only the JSON GeoJSON travels back over the wire.

    strong=True  → showcase polygon: bigger simplify tolerance, buffer round
                   joins, gives a soft "street-aligned" outline.
    strong=False → voronoi fallback: minimal cleanup (just MakeValid +
                   tiny simplify), preserves the cell geometry.
    """
    if strong:
        # Tolerances in degrees (EPSG:4326). ~1e-4 deg ≈ 11 m in Prešov.
        # Buffer +20 m / -20 m equivalent expressed in degrees.
        tol = "0.00025"           # ≈ 28 m
        buf_out = "0.00018"       # ≈ 20 m
        buf_in = "-0.00018"
        return f"""
        SELECT public.ST_AsGeoJSON(
          public.ST_Multi(
            public.ST_CollectionExtract(
              public.ST_MakeValid(
                public.ST_SimplifyPreserveTopology(
                  public.ST_Buffer(
                    public.ST_Buffer(
                      public.ST_MakeValid(geom_voronoi),
                      {buf_out},
                      'join=round'
                    ),
                    {buf_in},
                    'join=round'
                  ),
                  {tol}
                )
              ),
              3
            )
          )
        )::text AS geom_clean_geojson
        FROM skolske_obvody.districts
        WHERE id = '{district_id}'::uuid
        """
    else:
        tol = "0.00005"           # ≈ 5 m — barely visible cleanup
        return f"""
        SELECT public.ST_AsGeoJSON(
          public.ST_Multi(
            public.ST_CollectionExtract(
              public.ST_MakeValid(
                public.ST_SimplifyPreserveTopology(
                  public.ST_MakeValid(geom_voronoi),
                  {tol}
                )
              ),
              3
            )
          )
        )::text AS geom_clean_geojson
        FROM skolske_obvody.districts
        WHERE id = '{district_id}'::uuid
        """


def is_showcase(name: str) -> bool:
    return any(frag.lower() in name.lower() for frag in SHOWCASE_NAME_FRAGMENTS)


def main() -> int:
    districts = fetch_districts()
    if not districts:
        print("[build_clean_district_geom] no Prešov districts with geom_voronoi found — aborting")
        return 1

    features = []
    showcase_count = 0
    fallback_count = 0

    for d in districts:
        showcase = is_showcase(d["name"])
        rows = query_sql(smooth_polygon_sql(d["id"], strong=showcase))
        if not rows or not rows[0].get("geom_clean_geojson"):
            print(f"  ! {d['name']}: smoothing returned empty geometry, skipping")
            continue
        geom = json.loads(rows[0]["geom_clean_geojson"])

        method = "clean_polygon" if showcase else "voronoi_fallback"
        if showcase:
            showcase_count += 1
        else:
            fallback_count += 1

        features.append({
            "type": "Feature",
            "id": d["id"],
            "geometry": geom,
            "properties": {
                "id": d["id"],
                "name": d["name"],
                "method": method,
                "demo": True,
                "note": (
                    "Hand-tuned demo polygon (smoothed Voronoi) — not derived "
                    "from MŠSR Register adries."
                    if showcase
                    else "Voronoi fallback — replaced when street-snap pipeline ships."
                ),
            },
        })
        print(f"  + {d['name']}: {method}")

    fc = {
        "type": "FeatureCollection",
        "metadata": {
            "generator": "scripts/build_clean_district_geom.py",
            "sprint": "M-2",
            "showcase_count": showcase_count,
            "fallback_count": fallback_count,
            "total": len(features),
            "note": (
                f"{showcase_count} obvody majú demo clean polygóny (showcase), "
                f"zvyšok ({fallback_count}) je Voronoi rekonštrukcia z VZN textu."
            ),
        },
        "features": features,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[build_clean_district_geom] wrote {len(features)} features "
        f"({showcase_count} showcase + {fallback_count} fallback) → {OUT_PATH.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
