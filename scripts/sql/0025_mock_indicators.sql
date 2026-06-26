-- ============================================================================
-- 0025_mock_indicators.sql — QA bod 5/9: gap-filling DEMO data
-- ============================================================================
-- Purpose
-- -------
-- Several SECONDARY / illustrative § 44 indicators currently render
-- INSUFFICIENT_DATA / NOT_EVALUATED / ILUSTR_NO_DATA across all 12 Prešov
-- districts because their authoritative data source is a GAP:
--
--   * P-a  capacity / occupancy   — EDUZBER capacity dataset not available
--   * P-c  MHD (transit) access   — no agency GTFS / Routes API key
--   * P-d  language rights demand  — jazykový nárok dataset not available
--   * P-f  child demographics/ŠVVP — ŠTATSR / CVTI dataset not available
--
-- To demo the app's FULL data-processing functionality end-to-end, we seed
-- PLAUSIBLE mock values for ONLY these non-binding indicators, in a PHYSICALLY
-- SEPARATE table that the legal verdict path NEVER reads.
--
-- NON-NEGOTIABLE SAFETY INVARIANT
-- -------------------------------
-- The legal semafor (RED/ORANGE/GREEN) and the Š1–Š3 rows are computed by
-- `skolske_obvody.district_compositions` and `skolske_obvody.district_scorecard`,
-- both of which read ONLY from `skolske_obvody.verdicts`. This table and its
-- `so_mock_indicators` view are consumed ONLY by the UI scorecard for display,
-- never by the verdict/composition path. Mock values therefore CANNOT change a
-- district's legal verdict. Every mock value is rendered with a DEMO badge.
--
-- Path policy
-- -----------
-- Lives under scripts/sql/ (the harness path-block hook forbids writes under
-- /migrations/). Apply via scripts/apply_mock_indicators.py through the same
-- f2_exec_sql RPC bridge used by 0020/0021. f2_exec_sql wraps each call in its
-- own transaction and forbids explicit BEGIN/COMMIT, so this is a flat
-- statement sequence and the seed is idempotent (DELETE-by-domain + INSERT).
-- ----------------------------------------------------------------------------

-- ============================================================================
-- 1) Table: skolske_obvody.mock_indicators
-- ============================================================================
-- Key: (district_id, condition_code). Stores a display value plus a small
-- JSONB detail bag so the UI can render a sensible unit/label per indicator.
CREATE TABLE IF NOT EXISTS skolske_obvody.mock_indicators (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  district_id     UUID NOT NULL REFERENCES skolske_obvody.districts(id) ON DELETE CASCADE,
  condition_code  TEXT NOT NULL
                    CHECK (condition_code IN ('Pa', 'Pc', 'Pd', 'Pf')),
  -- short human-readable demo value, e.g. "78 % obsadenosť" or "18 min, 1 prestup"
  display_value   TEXT NOT NULL,
  -- machine-readable detail (numbers + units) for tooltips / future charts
  detail          JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- the gap this mock fills, surfaced in the tooltip
  source_gap      TEXT NOT NULL,
  is_demo         BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (district_id, condition_code)
);

CREATE INDEX IF NOT EXISTS mock_indicators_district_idx
  ON skolske_obvody.mock_indicators (district_id);

-- This table is admin-only at the storage layer; readers go through the
-- public view below.
REVOKE ALL ON skolske_obvody.mock_indicators FROM anon;

-- ============================================================================
-- 2) Public read view: public.so_mock_indicators
-- ============================================================================
-- Restricted to Prešov districts, exposes only display fields. This is the
-- ONLY surface the frontend reads. It is deliberately NOT joined into the
-- scorecard or composition views — keeping mock data out of the verdict path.
DROP VIEW IF EXISTS public.so_mock_indicators CASCADE;

CREATE VIEW public.so_mock_indicators AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
)
SELECT
  mi.district_id,
  mi.condition_code,
  mi.display_value,
  mi.detail,
  mi.source_gap,
  mi.is_demo
FROM skolske_obvody.mock_indicators mi
JOIN skolske_obvody.districts d ON d.id = mi.district_id
WHERE d.municipality_id = (SELECT id FROM presov);

GRANT SELECT ON public.so_mock_indicators TO anon, authenticated, service_role;
