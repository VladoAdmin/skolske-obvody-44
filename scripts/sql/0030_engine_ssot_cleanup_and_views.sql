-- 0030_engine_ssot_cleanup_and_views.sql
-- Phase 1 — remove ALL mock-override / accreted state so the engine re-run is
-- the single source, and scope findings_public to the CURRENT engine run only.
--
-- After this script, run:  python3 -m engine.runner
-- which repopulates verdicts + findings for exactly one engine_version.

-- ---------------------------------------------------------------------------
-- 1) Remove the mock verdict override (gen_demo_mode_seed / 0028 output) and
--    ALL accreted verdicts from prior engine runs. The engine re-run rewrites
--    the current run cleanly.
-- ---------------------------------------------------------------------------
-- Findings FK-reference verdicts, so delete findings first.
DELETE FROM skolske_obvody.findings WHERE id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2) Remove ALL accreted verdicts (mock override + prior engine runs).
-- ---------------------------------------------------------------------------
DELETE FROM skolske_obvody.verdicts WHERE id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3) Remove hand-seeded demo display rows in district_overlaps / district_islands.
--    These were illustration-only rows decoupled from the engine. With the engine
--    as SSOT, overlaps/islands shown on the map must derive from engine geometry,
--    not hand-seeded demo polygons.
-- ---------------------------------------------------------------------------
DELETE FROM skolske_obvody.district_overlaps WHERE is_demo = true;
DELETE FROM skolske_obvody.district_islands  WHERE is_demo = true;

-- ---------------------------------------------------------------------------
-- 4) Scope findings_public to the CURRENT engine run only (B2).
--    "Current run" = the engine_version whose findings have the most recent
--    created_at. This guarantees register == map == detail (all read the same
--    single latest run) without hardcoding a git hash.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS skolske_obvody.findings_public CASCADE;

CREATE VIEW skolske_obvody.findings_public AS
WITH presov AS (
    SELECT municipalities.id
    FROM skolske_obvody.municipalities
    WHERE municipalities.slug = 'presov'::text
    LIMIT 1
),
current_run AS (
    -- the engine_version with the newest finding (the latest engine run)
    SELECT engine_version
    FROM skolske_obvody.findings
    WHERE engine_version IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 1
)
SELECT f.id AS finding_id,
    f.district_id,
    d.name AS district_name,
    f.municipality_id,
    m.name AS municipality_name,
    f.condition_code,
    CASE f.condition_code
        WHEN 'S1'::text THEN 'Š1 — Adresy žiakov a obvod'::text
        WHEN 'S2'::text THEN 'Š2 — Topologické pokrytie'::text
        WHEN 'S3'::text THEN 'Š3 — Kompozícia obvodu'::text
        WHEN 'Pa'::text THEN 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km'::text
        WHEN 'Pb'::text THEN 'P-b — Pešia trasa'::text
        WHEN 'Pc'::text THEN 'P-c — MHD dostupnosť'::text
        WHEN 'Pd'::text THEN 'P-d — Bariéry (cesty, koľaje)'::text
        WHEN 'Pe'::text THEN 'P-e — Sociálny kontext (Atlas MRK)'::text
        WHEN 'Pf'::text THEN 'P-f — Demografia detí'::text
        ELSE f.condition_code
    END AS condition_label_sk,
    f.severity,
    CASE f.severity
        WHEN 'critical'::text THEN 5
        WHEN 'high'::text THEN 4
        WHEN 'medium'::text THEN 3
        WHEN 'low'::text THEN 2
        ELSE 1
    END AS severity_rank,
    f.status,
    skolske_obvody.sanitize_evidence(f.evidence_text, 200) AS evidence_public_text,
    CASE
        WHEN skolske_obvody.host_in_allowlist(v.provenance ->> 'source'::text)
            THEN v.provenance ->> 'source'::text
        ELSE NULL::text
    END AS provenance_source,
    f.created_at,
    f.is_demo,
    f.tag
FROM skolske_obvody.findings f
    JOIN skolske_obvody.districts d ON d.id = f.district_id
    JOIN skolske_obvody.municipalities m ON m.id = f.municipality_id
    LEFT JOIN skolske_obvody.verdicts v ON v.id = f.verdict_id
WHERE f.municipality_id = ((SELECT presov.id FROM presov))
  AND f.engine_version = (SELECT engine_version FROM current_run);

-- Restore grants on the recreated schema view.
GRANT SELECT ON skolske_obvody.findings_public TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 5) Recreate the public PostgREST wrapper views that DROP ... CASCADE removed.
--    so_findings_public  → register page (app/findings)
--    so_findings_panel   → map findings panel
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS public.so_findings_public CASCADE;
CREATE VIEW public.so_findings_public AS SELECT * FROM skolske_obvody.findings_public;
GRANT SELECT ON public.so_findings_public TO anon, authenticated, service_role;

DROP VIEW IF EXISTS public.so_findings_panel CASCADE;
CREATE VIEW public.so_findings_panel AS
SELECT
  fp.finding_id,
  fp.district_id,
  fp.district_name,
  fp.municipality_id,
  fp.municipality_name,
  fp.condition_code,
  fp.condition_label_sk,
  fp.severity,
  fp.severity_rank,
  fp.status,
  fp.evidence_public_text,
  fp.provenance_source,
  fp.created_at,
  fp.is_demo,
  fp.tag,
  public.ST_X(public.ST_Centroid(d.geom)) AS district_geom_centroid_lon,
  public.ST_Y(public.ST_Centroid(d.geom)) AS district_geom_centroid_lat
FROM skolske_obvody.findings_public fp
JOIN skolske_obvody.districts d ON d.id = fp.district_id
WHERE fp.severity IN ('critical', 'high', 'medium');
GRANT SELECT ON public.so_findings_panel TO anon, authenticated, service_role;
