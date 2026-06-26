# OSRM Routing Service — Školské obvody § 44

Walking profile routing for P-b (vzdialenosť/dochádzka) assessment.

## G-ROUTING Gate Requirements (PLAN §0.5)

Before Sprint 3 (P-b engine) can run, this gate must pass:
- OSRM deployed and reachable on `ROUTING_URL` (default: `http://localhost:5000`)
- Walking profile (`foot`) confirmed working
- Address snapping: PSK addresses snap to the road network
- Fallback: `LOW_DATA` returned when route unavailable (NEVER straight-line distance)

## Setup

```bash
# 1. Install Docker if not already installed
# 2. Process Slovakia OSM data (one-time, ~5-10 min, ~2GB disk)
chmod +x routing/setup.sh
./routing/setup.sh

# 3. Start OSRM server
docker compose -f routing/docker-compose.yml up -d

# 4. Verify health
curl http://localhost:5000/health
# Expected: {"status":"ok"}

# 5. Test route (Prešov city centre)
curl "http://localhost:5000/route/v1/foot/21.2400,49.0200;21.2611,49.0014?overview=false"
```

## Data Source

Slovakia OSM extract from Geofabrik:
- URL: https://download.geofabrik.de/europe/slovakia-latest.osm.pbf
- Size: ~150 MB
- License: ODbL (OpenStreetMap contributors)
- Updated: weekly

## Endpoints Used

| Endpoint | Usage |
|----------|-------|
| `GET /route/v1/foot/{coords}?overview=false` | Walking route for P-b |
| `GET /health` | Health check |

## Known Limitations

- OSRM foot profile uses OSM pedestrian/path/footway data
- Missing chodníky (sidewalks) in rural PSK areas may undercount actual walking distance
- No winter conditions or road closures
- Isochrones not natively supported (Sprint 3: add Valhalla or isochrone library)

## Fallback Policy

**CRITICAL**: Never compute or return straight-line (as-the-crow-flies) distance.
If OSRM is unavailable or returns no route:
- `RouteResult.status = "low_data"` or `"unavailable"`
- P-b verdict = `INCOMPLETE` (not a guessed pass/fail)
- This is enforced in `services/routing/client.ts`
