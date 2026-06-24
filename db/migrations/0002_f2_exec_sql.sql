-- ============================================================
-- f2_exec_sql: SECURITY DEFINER RPC bridge for programmatic DDL
-- ============================================================
-- Problem: Supabase PostgREST exposes only configured schemas, and
-- there is no API for F2 (this assistant) to run arbitrary DDL.
-- Manually applying every migration via the SQL Editor is friction.
--
-- Solution: a single SECURITY DEFINER function in `public` callable via
-- PostgREST RPC, gated to the `service_role` only. F2 holds the
-- service_role key in its env, so this is equivalent in trust to
-- the access F2 already has (service_role bypasses RLS), but newly
-- unlocks DDL.
--
-- Apply once. Never needed again.
-- ============================================================

CREATE OR REPLACE FUNCTION public.f2_exec_sql(query text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  ok_result jsonb;
BEGIN
  EXECUTE query;
  RETURN jsonb_build_object('ok', true);
EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object(
    'ok',       false,
    'sqlstate', SQLSTATE,
    'message',  SQLERRM
  );
END;
$$;

-- Lock execution to service_role only. anon/authenticated/PUBLIC must NEVER
-- be able to call this — it bypasses all RLS and runs as table owner.
REVOKE EXECUTE ON FUNCTION public.f2_exec_sql(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.f2_exec_sql(text) FROM anon;
REVOKE EXECUTE ON FUNCTION public.f2_exec_sql(text) FROM authenticated;
GRANT  EXECUTE ON FUNCTION public.f2_exec_sql(text) TO   service_role;

COMMENT ON FUNCTION public.f2_exec_sql(text) IS
  'Programmatic DDL bridge for F2 (Františka 2). service_role only. '
  'Runs arbitrary SQL as the function owner (postgres). Returns '
  '{ok: boolean, sqlstate?: text, message?: text}.';
