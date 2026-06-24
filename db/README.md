# Database Schema — Školské obvody § 44

Supabase (Postgres + PostGIS). Apply files in order via the Supabase SQL editor
or `psql $DATABASE_URL -f db/schema/<file>.sql`.

## Files

| File | Contents |
|------|----------|
| `00001_extensions.sql` | PostGIS, uuid-ossp, pg_trgm |
| `00002_core_tables.sql` | roles, user_roles, regions, municipalities, founders, schools, districts, address_points, datasets, dataset_events, verdicts, findings |
| `00003_vzn_tables.sql`  | vzns table + FK back to districts |
| `00004_rls.sql`         | RLS skeleton per PLAN §1 |

## How to apply (Supabase)

1. Open your Supabase project → SQL Editor.
2. Run files in order: 00001 → 00002 → 00003 → 00004.
3. Or use the CLI: `supabase db push` once `supabase/config.toml` is configured.

## Blockers

- **Supabase project not yet created** — F2/Vlado must create the project and
  provide `NEXT_PUBLIC_SUPABASE_URL` and keys. Then set them in `.env.local`.
- `auth.uid()` and `auth.role()` in RLS policies require Supabase Auth to be
  initialised. Sprint 5 wires JWT claim extraction.

## Design decisions

- All IDs are `UUID v4` (not serial) — safe for distributed ingestion.
- All timestamps are `TIMESTAMPTZ` (UTC).
- `districts.geom` has a `ST_IsValid` check constraint — invalid geometries are
  rejected at insert time (PostGIS guard, in addition to TypeScript validator).
- `verdicts` are append-only (no UPDATE). Recomputation inserts a new row;
  old verdicts are retained for reproducibility (`computed_at` + version fields).
- RLS is ON for all user-facing tables from Sprint 0. Service role bypasses RLS
  for ingestion writes.
