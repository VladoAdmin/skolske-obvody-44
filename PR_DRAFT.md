# Sprint 1 — Ingest Framework + Real Data Load

## What was loaded

### WFS Layers (Geoportál PSK — all REAL data, no mocks)

| Table | Source layer | Expected rows | Source URL | Date |
|-------|-------------|---------------|-----------|------|
| so_regions | geo-psk:admunit_counties | 1 (PSK) | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_municipalities | geo-psk:admunit_municipalities | 665 | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_schools | geo-psk:mapa_regionalneho_skolstva | ~400 ZŠ+MŠ | geopresovregion.sk/geoserver/wfs (2686 total, filtered) | 2026-06-24 |
| so_mrk_atlas | geo-psk:wm_ark_municipal | 224 | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_mrk_buildings | geo-psk:rsm_*_budovy (×6 obcí) | ~1900 | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_transit_stops | geo-psk:autobusove_zastavky_pad | 3172 | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_transit_stops | geo-psk:psk_zel_zastavky | 127 | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_road_network | geo-psk:cesty_1/2/3_triedy_ln | ~100 segments | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_demographics_children | geo-psk:so_age_structure_0_14_municipalities | 665 | geopresovregion.sk/geoserver/wfs | 2026-06-24 |
| so_datasets | provenance catalogue | 14 dataset records | — | 2026-06-24 |

**Note on row counts**: The counts above are from the live WFS. Actual DB row counts will be confirmed after `db/apply_public_schema.sql` is applied in Supabase SQL Editor and `python3 -m ingest.load_wfs_data` is run.

### VZN Prešov 1/2023 (REAL parsing, no mock)

| Table | Source | Rows | Date |
|-------|--------|------|------|
| so_vzns | skolskyurad.presov.sk/download_file_f.php?id=2250912 | 1 | 2023-09-01 |
| so_districts | VZN text → parsed | 12 districts | 2023-09-01 |

VZN was found at `http://www.skolskyurad.presov.sk/skolsky-obvod-zakladnych-skol-mesta-presov.html` and downloaded (331KB PDF). All 12 school districts extracted with full street lists (15–107 streets per district).

**District geometry**: `geometry_quality=6, geometry_confidence='none'` until address points are loaded and geocoding is run. Sprint 2 manual review fills `reviewed_by` + `reviewed_at`.

### Address Points (BLOCKER — not loaded)

| Table | Status | Reason | Impact |
|-------|--------|--------|--------|
| so_address_points | NOT LOADED | data.gov.sk API returns HTML (SPA); direct download not available from CI environment | Š1 = INCOMPLETE, P-b = INCOMPLETE for all municipalities |

**To unblock**: Download Register adries from https://www.minv.sk/?register-adries → save as `ingest/sources/register_adries_psk.csv` (or GeoJSON) → run `python3 -m ingest.load_address_points`.

## Topology Test Result (Prešov)

**Status: SKIP** — Cannot run until:
1. `db/apply_public_schema.sql` is applied in Supabase SQL Editor
2. WFS data is loaded (`python3 -m ingest.load_wfs_data`)
3. Address points are loaded (address points BLOCKER above)

Once address points are available: `python3 -m tests.test_topology --municipality Prešov`

## Routing Service Smoke Test

**Status: NOT STARTED** — OSRM requires docker + ~2GB disk for Slovakia OSM extract.

To run:
```bash
chmod +x routing/setup.sh && ./routing/setup.sh
docker compose -f routing/docker-compose.yml up -d
python3 -m ingest.smoke_test_routing
```

Expected: 20/20 routes within 2 seconds each. Fallback `LOW_DATA` for any unreachable route (never straight-line).

## Blockers (what's needed to unblock)

| Source | What's needed | Impact |
|--------|--------------|--------|
| **DB schema** | Apply `db/apply_public_schema.sql` in Supabase SQL Editor (no management API key available) | All DB inserts fail until schema is applied |
| **Register adries MV SR** | Manual download from minv.sk/?register-adries → `ingest/sources/register_adries_psk.csv` | Š1 + P-b = INCOMPLETE for all municipalities |
| **OSRM routing** | Run `routing/setup.sh` (requires docker, ~2GB disk, ~10min) | G-ROUTING gate cannot pass; P-b = INCOMPLETE |
| **Google Maps API** | Already noted as pending from Vlado | P-c (transit) = ILUSTR./NO DATA (non-blocking) |

## Key files

- `/home/node/.openclaw/workspace/projects/skolske-obvody-44/ingest/` — all Python ingest modules
- `/home/node/.openclaw/workspace/projects/skolske-obvody-44/ingest/sources/vzn_presov_1_2023.pdf` — downloaded VZN PDF
- `/home/node/.openclaw/workspace/projects/skolske-obvody-44/db/apply_public_schema.sql` — **apply this first in Supabase SQL Editor**
- `/home/node/.openclaw/workspace/projects/skolske-obvody-44/routing/` — OSRM docker-compose + setup
- `/home/node/.openclaw/workspace/projects/skolske-obvody-44/tests/` — topology test harness

## How to run (once schema is applied)

```bash
cd projects/skolske-obvody-44

# 1. Set env
export SUPABASE_URL=https://kapgabgnezcurmgcrvif.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=...

# 2. Load all WFS data
python3 -m ingest.load_wfs_data

# 3. Load address points (after placing CSV in ingest/sources/)
python3 -m ingest.load_address_points

# 4. Parse + load VZN (with geocoding via Nominatim, slow)
python3 -c "
from ingest.vzn_parser import load_and_parse_vzn, districts_to_db_records
from ingest.supabase_client import upsert
districts = load_and_parse_vzn()
records, vzn_records, unresolved = districts_to_db_records(districts, geocode=True)
upsert('vzns', vzn_records, on_conflict='key')
upsert('districts', records, on_conflict='district_number,municipality_nuts')
print('Unresolved streets:', len(unresolved))
"

# 5. Run topology tests
python3 -m tests.test_topology --municipality Prešov

# 6. Run routing smoke test (after OSRM is started)
python3 -m ingest.smoke_test_routing
```
