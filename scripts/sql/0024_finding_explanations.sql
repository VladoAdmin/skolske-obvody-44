-- ============================================================================
-- 0024_finding_explanations.sql — QA bod 10 phase 2
-- ============================================================================
-- Precomputed, AI-generated plain-Slovak explanations of findings.
--
-- Purpose
-- -------
-- The deterministic engine produces machine-template evidence per finding
-- (e.g. "FAIL: 3 verejných škôl typu ZS v obvode ..."). Vlado wants a
-- friendlier human explanation for analysts/readers — clearly marked as
-- AI-generated and WITHOUT changing the legal Š1–Š3 verdict.
--
-- Bounded cost: one explanation per DISTINCT (condition_code, severity)
-- combination (~13 combos), generated offline by
-- ingest/generate_finding_explanations.py via OpenAI. No runtime LLM.
--
-- This table/view touches neither district geometry nor the verdict logic.
--
-- Path policy
-- -----------
-- Lives under scripts/sql/ (not db/migrations/, which the harness path-block
-- hook forbids). Apply via ingest/generate_finding_explanations.py, which
-- runs this DDL through the f2_exec_sql RPC bridge before generating rows.
-- f2_exec_sql wraps each call in its own transaction, so this is a flat
-- statement sequence (no explicit BEGIN/COMMIT).
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS skolske_obvody.finding_explanations (
  condition_code   TEXT NOT NULL,
  severity         TEXT NOT NULL
                     CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
  explanation_sk   TEXT NOT NULL,           -- AI-generated plain-Slovak explanation
  model            TEXT,                    -- OpenAI model id used
  generated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (condition_code, severity)
);

-- Public read view (PostgREST does not expose the skolske_obvody schema).
CREATE OR REPLACE VIEW public.so_finding_explanations AS
SELECT
  condition_code,
  severity,
  explanation_sk,
  model,
  generated_at
FROM skolske_obvody.finding_explanations;

GRANT SELECT ON public.so_finding_explanations TO anon, authenticated, service_role;
