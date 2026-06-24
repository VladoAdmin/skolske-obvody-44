-- Schema file 00001: Enable required extensions
-- Apply via Supabase SQL editor or psql:
--   psql $DATABASE_URL -f db/schema/00001_extensions.sql

-- PostGIS: spatial geometry + geography types, ST_* functions
CREATE EXTENSION IF NOT EXISTS postgis;

-- uuid-ossp: uuid_generate_v4() for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pg_trgm: trigram indexes for fuzzy text search on VZN names
CREATE EXTENSION IF NOT EXISTS pg_trgm;
