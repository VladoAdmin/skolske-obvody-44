-- Skolske obvody § 44 — initial schema migration
-- Project: kapgabgnezcurmgcrvif  (Vlado's existing Supabase)
-- Schema: skolske_obvody  (isolated from public + str_v2)
-- Apply once: Supabase Dashboard → SQL Editor → New query → paste → Run

CREATE SCHEMA IF NOT EXISTS skolske_obvody;
SET search_path = skolske_obvody, extensions, public;

-- ========================================
-- 00001_extensions.sql
-- ========================================
-- Schema file 00001: Enable required extensions
-- Apply via Supabase SQL editor or psql:
--   psql $DATABASE_URL -f db/schema/00001_extensions.sql

-- PostGIS: spatial geometry + geography types, ST_* functions
CREATE EXTENSION IF NOT EXISTS postgis;

-- uuid-ossp: gen_random_uuid() for primary keys
-- uuid-ossp not needed: using built-in gen_random_uuid() (pgcrypto, ships with Supabase)

-- pg_trgm: trigram indexes for fuzzy text search on VZN names
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ========================================
-- 00002_core_tables.sql
-- ========================================
-- Schema file 00002: Core domain tables
-- Depends on: 00001_extensions.sql
-- Apply after PostGIS is enabled.

-- ============================================================
-- ROLES & AUTH (used by RLS policies in 00004_rls.sql)
-- ============================================================

CREATE TABLE IF NOT EXISTS roles (
  id   TEXT PRIMARY KEY,  -- 'analyst' | 'municipality_editor' | 'data_admin' | 'super_admin'
  label TEXT NOT NULL
);

INSERT INTO roles (id, label) VALUES
  ('analyst',             'Analytik (RÚŠS/ministerstvo)'),
  ('municipality_editor', 'Zriaďovateľ (sebakontrola)'),
  ('data_admin',          'Správca dát'),
  ('super_admin',         'Super-admin')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS user_roles (
  user_id        UUID NOT NULL,   -- auth.users.id from Supabase Auth
  role_id        TEXT NOT NULL REFERENCES roles(id),
  -- ABAC scope: municipality_editor is scoped to a single municipality
  municipality_id UUID,           -- NULL = global scope (analyst / admin)
  granted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  granted_by     UUID,            -- super_admin who granted this
  PRIMARY KEY (user_id, role_id)
);

-- ============================================================
-- GEOGRAPHY: regions → municipalities
-- ============================================================

CREATE TABLE IF NOT EXISTS regions (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code       TEXT UNIQUE NOT NULL,   -- e.g. 'PSK'
  name       TEXT NOT NULL,
  geom       GEOMETRY(MultiPolygon, 4326),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS municipalities (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id    UUID NOT NULL REFERENCES regions(id),
  code         TEXT UNIQUE NOT NULL,  -- REGOB / UPVS code
  name         TEXT NOT NULL,
  geom         GEOMETRY(MultiPolygon, 4326),
  -- Language minority flag (needed for P-d)
  minority_language TEXT,             -- 'HU' | 'RU' | NULL
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS municipalities_region_id_idx ON municipalities(region_id);
CREATE INDEX IF NOT EXISTS municipalities_geom_idx ON municipalities USING GIST(geom);

-- ============================================================
-- FOUNDERS (zriaďovatelia)
-- ============================================================

CREATE TABLE IF NOT EXISTS founders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id UUID NOT NULL REFERENCES municipalities(id),
  name            TEXT NOT NULL,
  ico             TEXT,               -- IČO (business ID)
  type            TEXT NOT NULL,      -- 'municipality' | 'state' | 'church' | 'private'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS founders_municipality_id_idx ON founders(municipality_id);

-- ============================================================
-- SCHOOLS (školy)
-- ============================================================

CREATE TABLE IF NOT EXISTS schools (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  founder_id      UUID REFERENCES founders(id),
  municipality_id UUID NOT NULL REFERENCES municipalities(id),
  -- From WFS / Register škôl
  eduid           TEXT UNIQUE,        -- EDUZBER / CVTI identifier
  name            TEXT NOT NULL,
  type            TEXT NOT NULL,      -- 'ZS' | 'MS' | 'ZUS'
  is_public       BOOLEAN NOT NULL DEFAULT true,
  teaching_language TEXT,             -- 'SK' | 'HU' | 'RU'
  capacity        INTEGER,            -- NULL if unavailable (EDUZBER GAP)
  student_count   INTEGER,            -- last known headcount
  geom            GEOMETRY(Point, 4326),
  source_name     TEXT,               -- dataset provenance
  source_date     DATE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS schools_municipality_id_idx ON schools(municipality_id);
CREATE INDEX IF NOT EXISTS schools_founder_id_idx ON schools(founder_id);
CREATE INDEX IF NOT EXISTS schools_geom_idx ON schools USING GIST(geom);

-- ============================================================
-- DISTRICTS / OBVODY (the core spatial objects)
-- ============================================================

CREATE TABLE IF NOT EXISTS districts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id UUID NOT NULL REFERENCES municipalities(id),
  school_id       UUID REFERENCES schools(id),  -- NULL if unresolved
  -- VZN metadata
  vzn_id          UUID,               -- FK to vzns table (00003)
  vzn_article     TEXT,               -- e.g. '§3 ods. 1 písm. a)'
  name            TEXT,               -- optional label from VZN
  school_type     TEXT NOT NULL,      -- 'ZS' | 'MS' (same as Š2 grouping)
  teaching_language TEXT,
  -- Geometry (WGS-84; re-project from VZN text via geocoding)
  geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
  -- Provenance
  source_name     TEXT NOT NULL,
  source_date     DATE NOT NULL,
  geometry_quality SMALLINT CHECK (geometry_quality BETWEEN 1 AND 10),
  reviewed_by     TEXT,               -- name of manual reviewer
  reviewed_at     TIMESTAMPTZ,
  geometry_confidence TEXT,           -- 'high' | 'medium' | 'low'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS districts_municipality_id_idx ON districts(municipality_id);
CREATE INDEX IF NOT EXISTS districts_school_id_idx ON districts(school_id);
CREATE INDEX IF NOT EXISTS districts_geom_idx ON districts USING GIST(geom);

-- Topology constraint: geometry must be valid (no self-intersections)
ALTER TABLE districts
  ADD CONSTRAINT districts_geom_valid
  CHECK (ST_IsValid(geom));

-- ============================================================
-- ADDRESS POINTS (adresné body — MV SR Register adries)
-- ============================================================

CREATE TABLE IF NOT EXISTS address_points (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id UUID NOT NULL REFERENCES municipalities(id),
  street          TEXT,
  house_number    TEXT,
  postal_code     TEXT,
  geom            GEOMETRY(Point, 4326) NOT NULL,
  -- Populated by spatial join with districts (computed)
  district_id     UUID REFERENCES districts(id),
  -- Data quality (adresné body are q9 when available)
  source_name     TEXT NOT NULL DEFAULT 'Register adries MV SR',
  source_date     DATE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS address_points_municipality_id_idx ON address_points(municipality_id);
CREATE INDEX IF NOT EXISTS address_points_district_id_idx ON address_points(district_id);
CREATE INDEX IF NOT EXISTS address_points_geom_idx ON address_points USING GIST(geom);

-- ============================================================
-- DATASETS + VERSIONS + PROVENANCE
-- ============================================================

CREATE TABLE IF NOT EXISTS datasets (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key          TEXT UNIQUE NOT NULL,   -- e.g. 'wfs_schools_psk', 'vzn_presov_1_2023'
  name         TEXT NOT NULL,
  source_url   TEXT,
  description  TEXT,
  -- DAMA quality dimensions (1–10)
  completeness SMALLINT CHECK (completeness BETWEEN 1 AND 10),
  validity     SMALLINT CHECK (validity BETWEEN 1 AND 10),
  -- Versioning
  version      TEXT NOT NULL DEFAULT '0',
  fetched_at   TIMESTAMPTZ,
  source_date  DATE,
  -- Status
  status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'staged', 'validated', 'active', 'rejected', 'superseded')),
  activated_at TIMESTAMPTZ,
  activated_by UUID,
  -- Audit trail
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Provenance log (append-only)
CREATE TABLE IF NOT EXISTS dataset_events (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id),
  event_type TEXT NOT NULL,  -- 'fetch' | 'validate' | 'activate' | 'reject'
  actor_id   UUID,
  notes      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- VERDICTS (predpočítané, verziované)
-- ============================================================

CREATE TABLE IF NOT EXISTS verdicts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  district_id         UUID NOT NULL REFERENCES districts(id),
  condition_code      TEXT NOT NULL,   -- 'S1' | 'S2' | 'S3' | 'Pa' | 'Pb' | 'Pc' | 'Pd' | 'Pe' | 'Pf'
  -- Five-tuple
  value               TEXT NOT NULL,   -- 'pass' | 'fail' | 'incomplete' | 'risk' | 'low_data' | 'signal' | 'no_signal' | 'not_evaluated'
  confidence          NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
  data_completeness   NUMERIC(4,3) CHECK (data_completeness BETWEEN 0 AND 1),
  provenance          JSONB NOT NULL,  -- {source, fetched_at, transformations[]}
  methodology         JSONB NOT NULL,  -- {rule, version, threshold}
  -- Status flags (gatekeeping — PLAN §5 PRD)
  is_illustrative     BOOLEAN NOT NULL DEFAULT false,   -- ILUSTR.
  is_proxy            BOOLEAN NOT NULL DEFAULT false,   -- PROXY
  is_mock             BOOLEAN NOT NULL DEFAULT false,   -- MOCK
  -- Versioning
  dataset_version     TEXT NOT NULL,
  methodology_version TEXT NOT NULL,
  engine_version      TEXT NOT NULL,
  computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Drill-down evidence
  evidence_text       TEXT,           -- human-readable explanation
  evidence_refs       JSONB           -- [{vzn_article, law_article, rule_ref}]
);

CREATE INDEX IF NOT EXISTS verdicts_district_id_idx ON verdicts(district_id);
CREATE INDEX IF NOT EXISTS verdicts_condition_code_idx ON verdicts(condition_code);
CREATE INDEX IF NOT EXISTS verdicts_computed_at_idx ON verdicts(computed_at);

-- ============================================================
-- FINDINGS REGISTER (register nálezov)
-- ============================================================

CREATE TABLE IF NOT EXISTS findings (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  verdict_id     UUID NOT NULL REFERENCES verdicts(id),
  district_id    UUID NOT NULL REFERENCES districts(id),
  municipality_id UUID NOT NULL REFERENCES municipalities(id),
  condition_code TEXT NOT NULL,
  severity       TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
  status         TEXT NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'acknowledged', 'resolved', 'wont_fix')),
  evidence_text  TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS findings_municipality_id_idx ON findings(municipality_id);
CREATE INDEX IF NOT EXISTS findings_severity_idx ON findings(severity);
CREATE INDEX IF NOT EXISTS findings_status_idx ON findings(status);

-- ========================================
-- 00003_vzn_tables.sql
-- ========================================
-- Schema file 00003: VZN (municipal ordinance) tables
-- Depends on: 00002_core_tables.sql

CREATE TABLE IF NOT EXISTS vzns (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id UUID NOT NULL REFERENCES municipalities(id),
  reference       TEXT NOT NULL,      -- e.g. 'VZN 1/2023'
  title           TEXT,
  effective_date  DATE,
  url             TEXT,
  raw_text        TEXT,
  -- Scraping metadata
  hash            TEXT,               -- SHA-256 of raw_text for change detection
  scraped_at      TIMESTAMPTZ,
  scrape_status   TEXT NOT NULL DEFAULT 'pending'
                    CHECK (scrape_status IN ('pending', 'ok', 'error', 'changed')),
  -- Parsing status
  parse_status    TEXT NOT NULL DEFAULT 'pending'
                    CHECK (parse_status IN ('pending', 'parsed', 'manual_review', 'failed')),
  parsed_at       TIMESTAMPTZ,
  parsed_by       TEXT,               -- 'auto' | 'manual:username'
  -- Provenance
  dataset_id      UUID REFERENCES datasets(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (municipality_id, reference)
);

CREATE INDEX IF NOT EXISTS vzns_municipality_id_idx ON vzns(municipality_id);

-- Add FK from districts → vzns (cross-reference after vzns table exists)
ALTER TABLE districts
  ADD CONSTRAINT fk_districts_vzn
  FOREIGN KEY (vzn_id) REFERENCES vzns(id)
  DEFERRABLE INITIALLY DEFERRED;

-- ========================================
-- 00004_rls.sql
-- ========================================
-- Schema file 00004: Row-Level Security (RLS) skeleton
-- Depends on: 00002_core_tables.sql
--
-- Sprint 0: define RLS policies per PLAN §1.
-- Sprint 5 (auth/ABAC): extend with actual Supabase Auth JWT claims.
--
-- IMPORTANT: Enable RLS on all tables that contain user-scoped data.
-- Tables without RLS are readable by anyone with DB access — review before prod.

-- ============================================================
-- Enable RLS
-- ============================================================

ALTER TABLE districts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE address_points  ENABLE ROW LEVEL SECURITY;
ALTER TABLE verdicts        ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings        ENABLE ROW LEVEL SECURITY;
ALTER TABLE vzns            ENABLE ROW LEVEL SECURITY;
ALTER TABLE municipalities  ENABLE ROW LEVEL SECURITY;
ALTER TABLE schools         ENABLE ROW LEVEL SECURITY;
ALTER TABLE founders        ENABLE ROW LEVEL SECURITY;
ALTER TABLE datasets        ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles      ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Helper: check caller role from user_roles table
-- Sprint 5 replaces this with JWT claim extraction.
-- ============================================================

CREATE OR REPLACE FUNCTION current_user_role()
RETURNS TEXT
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  -- Returns the highest-privilege role for auth.uid()
  -- Priority: super_admin > data_admin > analyst > municipality_editor
  SELECT role_id
  FROM user_roles
  WHERE user_id = auth.uid()
  ORDER BY CASE role_id
    WHEN 'super_admin'         THEN 1
    WHEN 'data_admin'          THEN 2
    WHEN 'analyst'             THEN 3
    WHEN 'municipality_editor' THEN 4
    ELSE 5
  END
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION current_municipality_id()
RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT municipality_id
  FROM user_roles
  WHERE user_id = auth.uid()
    AND role_id = 'municipality_editor'
  LIMIT 1;
$$;

-- ============================================================
-- DISTRICTS: analyst/admin = all; municipality_editor = own only
-- ============================================================

-- Analysts (RÚŠS, ministry) read all districts
CREATE POLICY districts_analyst_read ON districts
  FOR SELECT
  USING (
    current_user_role() IN ('analyst', 'data_admin', 'super_admin')
  );

-- Municipality editors read only their own municipality's districts
CREATE POLICY districts_editor_read ON districts
  FOR SELECT
  USING (
    current_user_role() = 'municipality_editor'
    AND municipality_id = current_municipality_id()
  );

-- Only data_admin / super_admin can insert/update/delete districts
CREATE POLICY districts_admin_write ON districts
  FOR ALL
  USING (current_user_role() IN ('data_admin', 'super_admin'))
  WITH CHECK (current_user_role() IN ('data_admin', 'super_admin'));

-- ============================================================
-- VERDICTS: read-only for analyst + editor (scoped)
-- ============================================================

CREATE POLICY verdicts_analyst_read ON verdicts
  FOR SELECT
  USING (
    current_user_role() IN ('analyst', 'data_admin', 'super_admin')
  );

CREATE POLICY verdicts_editor_read ON verdicts
  FOR SELECT
  USING (
    current_user_role() = 'municipality_editor'
    AND district_id IN (
      SELECT id FROM districts
      WHERE municipality_id = current_municipality_id()
    )
  );

-- Only the system (service role) writes verdicts
CREATE POLICY verdicts_system_write ON verdicts
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- ============================================================
-- MUNICIPALITIES: everyone reads (public reference data)
-- ============================================================

CREATE POLICY municipalities_public_read ON municipalities
  FOR SELECT
  USING (true);

-- Only admin writes
CREATE POLICY municipalities_admin_write ON municipalities
  FOR ALL
  USING (current_user_role() IN ('data_admin', 'super_admin'))
  WITH CHECK (current_user_role() IN ('data_admin', 'super_admin'));

-- ============================================================
-- SCHOOLS + FOUNDERS: readable by all authenticated
-- ============================================================

CREATE POLICY schools_auth_read ON schools
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

CREATE POLICY founders_auth_read ON founders
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

-- ============================================================
-- USER_ROLES: only super_admin can manage
-- ============================================================

CREATE POLICY user_roles_self_read ON user_roles
  FOR SELECT
  USING (user_id = auth.uid() OR current_user_role() = 'super_admin');

CREATE POLICY user_roles_admin_write ON user_roles
  FOR ALL
  USING (current_user_role() = 'super_admin')
  WITH CHECK (current_user_role() = 'super_admin');

-- ============================================================
-- DATASETS: admin writes; analysts/editors read active only
-- ============================================================

CREATE POLICY datasets_active_read ON datasets
  FOR SELECT
  USING (
    status = 'active'
    OR current_user_role() IN ('data_admin', 'super_admin')
  );

CREATE POLICY datasets_admin_write ON datasets
  FOR ALL
  USING (current_user_role() IN ('data_admin', 'super_admin'))
  WITH CHECK (current_user_role() IN ('data_admin', 'super_admin'));

