-- 0049_engine_metadata_street_coverage.sql
-- VLA-18 — SummaryStrip real/mock/vzn_gap street counters.
--
-- WHY
--   Investigation (log/2026-07-11-vla-18-datagap-mock.md) found VLA-20 +
--   the existing VLA-14 vzn_gap classifier already give 100% street-level
--   coverage (377 VZN-matched + 23 vzn_gap = 400/400 register streets, 0
--   unaccounted). No mock district-assignment mechanism is needed. The
--   remaining AC gap is purely reporting: the SummaryStrip must show how
--   many streets are real / mock / vzn_gap.
--
-- WHAT
--   Extends the existing skolske_obvody.engine_metadata VIEW (defined in
--   db/migrations/0010_sprint_c_read_views.sql) with two more live-computed
--   aggregate columns:
--     * street_real_count — register streets matched to a VZN assignment
--       (drawn as a coloured street line). Same NORM + join shape as
--       engine/coverage_gaps.py's gap query, inverted (matched, not gap).
--     * street_mock_count — count of is_demo=TRUE rows in
--       street_coverage_gaps. 0 today (no mock street rows exist); wired
--       so a future demo row would surface automatically, never hardcoded.
--   vzn_gap count is already available client-side from so_street_coverage_gaps
--   (existing CoverageGapCounts in components/map/summary-strip.tsx) — not
--   duplicated here.
--
--   public.so_engine_metadata (db/migrations/0011) is `SELECT * FROM
--   skolske_obvody.engine_metadata`. Postgres freezes a `SELECT *` view's
--   column list at CREATE time — CREATE OR REPLACE on the base view does
--   NOT propagate new columns through it. Verified live: querying
--   skolske_obvody.engine_metadata directly returned the new columns, but
--   public.so_engine_metadata errored "column street_real_count does not
--   exist" until the wrapper was dropped + recreated below (same DROP
--   CASCADE + CREATE + GRANT shape as 0011's original).
--
-- Apply:  python3 scripts/apply_sql.py scripts/sql/0049_engine_metadata_street_coverage.sql

CREATE OR REPLACE VIEW skolske_obvody.engine_metadata AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
),
vzn_norm AS (
  SELECT DISTINCT
    regexp_replace(
      regexp_replace(
        regexp_replace(
          lower(unaccent(
            replace(replace(v.street, 'Arm. gen.', 'Armádneho generála'), 'č.', '')
          )),
          '^ulica\s+|\s+ulica$', '', 'g'),
        '[.]', ' ', 'g'),
      '\s+', ' ', 'g') AS n
  FROM skolske_obvody.vzn_street_ranges v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  WHERE d.municipality_id = (SELECT id FROM presov)
),
reg_norm AS (
  SELECT DISTINCT ulica_norm AS n
  FROM skolske_obvody.register_adries_clean
  WHERE ulica_norm IS NOT NULL AND ulica_norm <> ''
),
street_counts AS (
  SELECT
    (SELECT count(*) FROM reg_norm r WHERE EXISTS (
       SELECT 1 FROM vzn_norm v WHERE v.n = r.n)) AS street_real_count,
    (SELECT count(*) FROM skolske_obvody.street_coverage_gaps g
       WHERE g.municipality_id = (SELECT id FROM presov)
         AND g.is_demo = TRUE) AS street_mock_count
)
SELECT
  MAX(v.dataset_version) AS dataset_version,
  MAX(v.methodology_version) AS methodology_version,
  MAX(v.engine_version) AS engine_version,
  MAX(v.computed_at) AS last_engine_run_at,
  COUNT(v.id) AS verdicts_count,
  COUNT(DISTINCT d.id) AS districts_count,
  COUNT(DISTINCT d.school_id) AS schools_count,
  COUNT(DISTINCT f.id) FILTER (WHERE f.status = 'open') AS open_findings_count,
  (SELECT street_real_count FROM street_counts) AS street_real_count,
  (SELECT street_mock_count FROM street_counts) AS street_mock_count
FROM skolske_obvody.verdicts v
JOIN skolske_obvody.districts d ON d.id = v.district_id
LEFT JOIN skolske_obvody.findings f ON f.district_id = d.id
WHERE d.municipality_id = (SELECT id FROM presov);

-- Public wrapper (db/migrations/0011 shape): must be dropped + recreated so
-- its SELECT * column list picks up street_real_count/street_mock_count.
DROP VIEW IF EXISTS public.so_engine_metadata CASCADE;
CREATE VIEW public.so_engine_metadata AS SELECT * FROM skolske_obvody.engine_metadata;
GRANT SELECT ON public.so_engine_metadata TO anon;
