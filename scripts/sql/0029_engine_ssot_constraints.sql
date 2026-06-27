-- 0029_engine_ssot_constraints.sql
-- Phase 1 — make the ENGINE the single source of truth.
--
-- B1: verdicts & findings lack UNIQUE(district_id, condition_code, engine_version),
--     so engine runner's ON CONFLICT silently fails and rows accrete across runs.
--     Add the unique constraints so the UPSERT actually overwrites in place.
--
-- This script is idempotent: it first de-duplicates any pre-existing rows
-- (keeping the newest computed_at / created_at per key), then adds the constraint
-- only if missing.

-- ---------------------------------------------------------------------------
-- verdicts: de-dup then UNIQUE(district_id, condition_code, engine_version)
-- ---------------------------------------------------------------------------
DELETE FROM skolske_obvody.verdicts v
USING (
    SELECT id,
           row_number() OVER (
               PARTITION BY district_id, condition_code, engine_version
               ORDER BY computed_at DESC, id DESC
           ) AS rn
    FROM skolske_obvody.verdicts
) dup
WHERE v.id = dup.id AND dup.rn > 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'verdicts_district_condition_engine_uniq'
    ) THEN
        ALTER TABLE skolske_obvody.verdicts
            ADD CONSTRAINT verdicts_district_condition_engine_uniq
            UNIQUE (district_id, condition_code, engine_version);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- findings: de-dup then UNIQUE(district_id, condition_code, engine_version)
-- NOTE: demo findings (is_demo=true, tag like 'demo:%') historically used a
-- NULL engine_version and are NOT engine-derived. Phase 1 removes them entirely
-- (handled in 0030), but to make the constraint addable we first de-dup on the
-- key as-is. NULL engine_version values are distinct under a plain UNIQUE, so
-- they will not collide.
-- ---------------------------------------------------------------------------
DELETE FROM skolske_obvody.findings f
USING (
    SELECT id,
           row_number() OVER (
               PARTITION BY district_id, condition_code, engine_version
               ORDER BY created_at DESC, id DESC
           ) AS rn
    FROM skolske_obvody.findings
    WHERE engine_version IS NOT NULL
) dup
WHERE f.id = dup.id AND dup.rn > 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'findings_district_condition_engine_uniq'
    ) THEN
        ALTER TABLE skolske_obvody.findings
            ADD CONSTRAINT findings_district_condition_engine_uniq
            UNIQUE (district_id, condition_code, engine_version);
    END IF;
END $$;
