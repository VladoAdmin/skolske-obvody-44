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
