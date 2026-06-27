-- 0031_demo_input_columns.sql
-- Phase 2/3 — add INPUT-layer columns the reconciled checkers read.
-- All demo content enters through these real columns (flagged is_demo / metadata),
-- the engine recomputes, views render engine output. No hand-written verdicts.
--
-- Idempotent.

-- P-a: mark a geocoded address as a DEMO (fabricated) address so the engine can
-- demonstrate a >2 km case while keeping it clearly flagged.
ALTER TABLE skolske_obvody.house_geocodes
    ADD COLUMN IF NOT EXISTS is_demo boolean NOT NULL DEFAULT false;

-- P-f: schools.metadata holds the demo flag for capacity/enrolment so an
-- overcrowding SIGNAL can be demonstrated and badged as DEMO.
ALTER TABLE skolske_obvody.schools
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

-- P-e: mark MRK locality buildings as DEMO so an explicit inclusion case can be
-- demonstrated for one district while staying clearly flagged.
ALTER TABLE skolske_obvody.mrk_buildings
    ADD COLUMN IF NOT EXISTS is_demo boolean NOT NULL DEFAULT false;
