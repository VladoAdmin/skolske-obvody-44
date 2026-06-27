-- 0035_finding_explanations_by_value.sql
-- Part C — AI finding explanations must MATCH the verdict. Re-key the table from
-- (condition_code, severity) to (condition_code, value) so the UI looks up the
-- explanation for the district's ACTUAL verdict value. This removes the
-- "...je to problém" text on a PASS row, and the "1% menšina + barrier"
-- contradiction (which came from a single per-code explanation shown regardless
-- of value).
--
-- Idempotent. Drops the old severity-keyed table and recreates value-keyed.

DROP VIEW IF EXISTS public.so_finding_explanations CASCADE;
DROP TABLE IF EXISTS skolske_obvody.finding_explanations CASCADE;

CREATE TABLE skolske_obvody.finding_explanations (
  condition_code   TEXT NOT NULL,
  value            TEXT NOT NULL,            -- verdict value: PASS/FAIL/SIGNAL/...
  explanation_sk   TEXT NOT NULL,           -- AI-generated plain-Slovak explanation
  model            TEXT,
  generated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (condition_code, value)
);

CREATE OR REPLACE VIEW public.so_finding_explanations AS
SELECT condition_code, value, explanation_sk, model, generated_at
FROM skolske_obvody.finding_explanations;

GRANT SELECT ON public.so_finding_explanations TO anon, authenticated, service_role;
