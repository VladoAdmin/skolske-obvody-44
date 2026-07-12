-- 0051_municipality_inhabited_areas.sql
-- VLA-31 — Mapa obcí spoločného obvodu: obývaná oblasť, nie celé katastrálne
-- územie.
--
-- WHY
--   VLA-21 (0050_shared_municipality_areas.sql) rendered each shared
--   municipality's FULL cadastral/administrative polygon
--   (skolske_obvody.municipalities.geom) — fields, meadows and empty land
--   included. Client feedback: "Hranice obcí sa nemyslí katastrálne územie,
--   ale hranice ulíc v samotnej obci. Nie polia a lúky okolo, ale adresy
--   domov kde žijú ľudia." (municipality boundary should mean street-level
--   boundaries within the settlement, not the cadastral area).
--
--   Checked live before building this: house_geocodes / address_points (the
--   tables backing the existing "Adresné body obvodov" point layer) have
--   ZERO rows for all 21 shared municipalities — both are scoped to the
--   school districts' own municipality (Prešov city), not these VZN-listed
--   neighbour villages, which sit outside that ingestion scope entirely.
--   osm_street_lines (the district streets-pivot source) is likewise scoped
--   to a single Overpass query bounded to Prešov city — verified live it
--   does not spatially intersect these municipalities at all (0-4 stray
--   boundary-crossing segments, not real per-village coverage). Named-street
--   OSM tagging is also inconsistent for small villages (Bzenov, Zlatá Baňa:
--   0 named highway ways each, verified live) — real Slovak villages often
--   address by súpisné číslo only, no formal ulica system.
--
--   Real OSM BUILDING footprints exist for all 21 (190-2588 buildings each,
--   verified live via ingest/fetch_osm_buildings.py, total 20889) — this is
--   the only universal real-data signal available for "where people live"
--   in these municipalities. No fabrication: every polygon here is a real
--   OSM building footprint, buffered to merge adjacent structures into one
--   readable shape and clipped to the real cadastral boundary as a safety
--   net (never draws outside the actual administrative territory).
--
-- WHAT
--   New table skolske_obvody.municipality_inhabited_areas, ONE row per
--   municipality: ST_Union of each building footprint buffered 25m
--   (geography-cast for a metric buffer), intersected with the real
--   cadastral polygon. Precomputed (not a live view) because the
--   buffer+union aggregation over ~20889 buildings takes ~3s — same
--   "compute once into a table, view just reads it" convention as
--   district_longest_routes / district_islands elsewhere in this schema.
--   Re-run this file after any ingest/fetch_osm_buildings.py refresh.
--
--   so_shared_municipality_areas is rebuilt to source geom_geojson from
--   this new table instead of the raw municipality polygon. A municipality
--   with no precomputed row (zero OSM buildings fetched) renders
--   geom_geojson = NULL — the frontend already skips NULL geometries
--   (`if (!area.geom_geojson) return`, components/region-map.client.tsx) —
--   it NEVER falls back to the full cadastral polygon and NEVER fabricates
--   a shape. building_count is exposed so the UI can show real provenance
--   ("aproximácia z N budov OSM"), not an unlabelled shape.
--
-- Apply: python3 scripts/apply_sql.py scripts/sql/0051_municipality_inhabited_areas.sql

CREATE TABLE IF NOT EXISTS skolske_obvody.municipality_inhabited_areas (
  municipality_id UUID PRIMARY KEY REFERENCES skolske_obvody.municipalities(id),
  geom public.geometry(MultiPolygon, 4326),
  building_count INTEGER NOT NULL,
  computed_at TIMESTAMPTZ DEFAULT now()
);

TRUNCATE skolske_obvody.municipality_inhabited_areas;

INSERT INTO skolske_obvody.municipality_inhabited_areas (municipality_id, geom, building_count)
SELECT
  m.id,
  public.ST_Multi(
    public.ST_Intersection(
      public.ST_Union(public.ST_Buffer(b.geom::public.geography, 25)::public.geometry),
      m.geom
    )
  ) AS geom,
  count(*) AS building_count
FROM skolske_obvody.municipalities m
JOIN skolske_obvody.osm_buildings b
  ON b.municipality_id = m.id
  AND public.ST_Intersects(b.geom, m.geom)
GROUP BY m.id, m.geom;

CREATE INDEX IF NOT EXISTS municipality_inhabited_areas_gix
  ON skolske_obvody.municipality_inhabited_areas USING GIST (geom);

DROP VIEW IF EXISTS public.so_shared_municipality_areas;
CREATE VIEW public.so_shared_municipality_areas AS
SELECT
  d.id AS district_id,
  d.name AS district_name,
  m.id AS municipality_id,
  m.name AS municipality_name,
  (
    SELECT value
    FROM jsonb_each_text(COALESCE(d.metadata->'shared_municipality_grades', '{}'::jsonb))
    WHERE lower(unaccent(key)) = lower(unaccent(sm.name))
    LIMIT 1
  ) AS grade_range,
  public.ST_AsGeoJSON(mia.geom)::jsonb AS geom_geojson,
  mia.building_count
FROM skolske_obvody.districts d
JOIN skolske_obvody.municipalities home ON home.id = d.municipality_id
CROSS JOIN LATERAL jsonb_array_elements_text(
  COALESCE(d.metadata->'shared_municipalities', '[]'::jsonb)
) AS sm(name)
JOIN LATERAL (
  SELECT cand.id, cand.name, cand.geom
  FROM skolske_obvody.municipalities cand
  WHERE lower(unaccent(cand.name)) = lower(unaccent(sm.name))
    AND cand.geom IS NOT NULL
  ORDER BY public.ST_DistanceSphere(
    public.ST_Centroid(cand.geom), public.ST_Centroid(home.geom)
  ) ASC
  LIMIT 1
) m ON true
LEFT JOIN skolske_obvody.municipality_inhabited_areas mia ON mia.municipality_id = m.id;

GRANT SELECT ON public.so_shared_municipality_areas TO anon, authenticated, service_role;
