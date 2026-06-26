-- Topology test contract — G-DATA gate
-- Run these queries in sequence; all must return 0 rows for PASS.
--
-- Usage: paste into Supabase SQL Editor, or run via test_topology.py harness.
-- Schema: public (tables have so_ prefix)
--
-- PASS criteria (per PLAN §0.5 G-DATA gate):
--   T1: ST_IsValid on every district geometry → 0 invalid
--   T2: Address coverage — every address point in exactly 1 district → 0 uncovered + 0 multi-assigned
--   T3: No overlaps among same-type+language districts → 0 overlaps
--
-- Results with > 0 rows = FAIL (with explanation in row).

------------------------------------------------------------------------
-- T1: Geometry validity check
------------------------------------------------------------------------
-- Expected: 0 rows (all geometries valid)
SELECT
  d.district_number,
  d.school_name,
  d.municipality_name,
  'INVALID_GEOMETRY' AS failure_type,
  ST_IsValidReason(d.geom) AS reason
FROM so_districts d
WHERE d.geom IS NOT NULL
  AND NOT ST_IsValid(d.geom);

------------------------------------------------------------------------
-- T2a: Uncovered address points (Š1 — no district covers them)
--      Only checks addresses for municipalities that have districts loaded.
------------------------------------------------------------------------
-- Expected: 0 rows (every address is in at least 1 district)
-- FAIL → Š1 coverage gap exists
SELECT
  ap.id,
  ap.street,
  ap.house_number,
  ap.municipality_code,
  'UNCOVERED_ADDRESS' AS failure_type
FROM so_address_points ap
WHERE ap.municipality_code IN (
  SELECT DISTINCT municipality_nuts
  FROM so_districts
  WHERE geom IS NOT NULL
)
AND NOT EXISTS (
  SELECT 1 FROM so_districts d
  WHERE d.municipality_nuts = ap.municipality_code
    AND ST_Covers(d.geom, ap.geom)
);

------------------------------------------------------------------------
-- T2b: Multi-assigned address points (Š1 — same address in >1 district)
--      This is an explicit FAIL per PLAN: "multi-assignment = explicit FAIL, not silent"
------------------------------------------------------------------------
-- Expected: 0 rows
SELECT
  ap.id,
  ap.street,
  ap.house_number,
  ap.municipality_code,
  COUNT(d.id) AS district_count,
  'MULTI_ASSIGNED_ADDRESS' AS failure_type,
  STRING_AGG(d.school_name, ' | ') AS districts
FROM so_address_points ap
JOIN so_districts d
  ON d.municipality_nuts = ap.municipality_code
  AND ST_Covers(d.geom, ap.geom)
GROUP BY ap.id, ap.street, ap.house_number, ap.municipality_code
HAVING COUNT(d.id) > 1;

------------------------------------------------------------------------
-- T3: Overlap check (Š2 — same school_type + teaching_language districts must not overlap)
------------------------------------------------------------------------
-- Expected: 0 rows
SELECT
  a.district_number AS district_a,
  b.district_number AS district_b,
  a.municipality_name,
  a.school_type,
  a.teaching_language,
  'OVERLAP' AS failure_type,
  ST_Area(ST_Intersection(a.geom, b.geom)::geography) AS overlap_area_m2
FROM so_districts a
JOIN so_districts b
  ON a.id < b.id
  AND a.municipality_name = b.municipality_name
  AND a.school_type = b.school_type
  AND a.teaching_language = b.teaching_language
  AND a.geom IS NOT NULL
  AND b.geom IS NOT NULL
  AND ST_Intersects(a.geom, b.geom)
  -- Tolerance: ignore sub-1m2 slivers from geocoding imprecision
  AND ST_Area(ST_Intersection(a.geom, b.geom)::geography) > 1.0;

------------------------------------------------------------------------
-- Summary counts (informational — run after the above tests)
------------------------------------------------------------------------
SELECT
  'so_regions' AS table_name, COUNT(*) AS row_count FROM so_regions
UNION ALL SELECT 'so_municipalities', COUNT(*) FROM so_municipalities
UNION ALL SELECT 'so_schools', COUNT(*) FROM so_schools
UNION ALL SELECT 'so_districts', COUNT(*) FROM so_districts
UNION ALL SELECT 'so_address_points', COUNT(*) FROM so_address_points
UNION ALL SELECT 'so_mrk_atlas', COUNT(*) FROM so_mrk_atlas
UNION ALL SELECT 'so_transit_stops', COUNT(*) FROM so_transit_stops
UNION ALL SELECT 'so_vzns', COUNT(*) FROM so_vzns
UNION ALL SELECT 'so_datasets', COUNT(*) FROM so_datasets;
