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
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  code       TEXT UNIQUE NOT NULL,   -- e.g. 'PSK'
  name       TEXT NOT NULL,
  geom       GEOMETRY(MultiPolygon, 4326),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS municipalities (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
