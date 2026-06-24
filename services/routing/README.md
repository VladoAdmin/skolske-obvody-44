# Routing Service — OSRM / Valhalla over OSM SK

This service provides walking and driving routing for P-b (distance/travel time)
and isochrone generation used in the compliance engine.

## Required: GATE G-ROUTING (PLAN §0.5)

Before Sprint 3 (P-b implementation) the following gate must pass:

1. OSRM or Valhalla is deployed and reachable at `ROUTING_URL`.
2. Walking profile is confirmed working (test: Prešov city centre → nearest school).
3. Address snapping test passes (addresses snap onto the road network, not into voids).
4. Fallback `LOW_DATA` is returned when a route is unavailable (NEVER straight-line distance).

## Option A — OSRM (recommended for Sprint 0/1)

### Docker Compose (quickstart)

```bash
# 1. Download Slovakia OSM extract
mkdir -p routing/data
wget -O routing/data/slovakia-latest.osm.pbf \
  https://download.geofabrik.de/europe/slovakia-latest.osm.pbf

# 2. Pre-process for OSRM (foot profile)
docker run -t -v $(pwd)/routing/data:/data \
  osrm/osrm-backend:latest \
  osrm-extract -p /opt/foot.lua /data/slovakia-latest.osm.pbf

docker run -t -v $(pwd)/routing/data:/data \
  osrm/osrm-backend:latest \
  osrm-partition /data/slovakia-latest.osrm

docker run -t -v $(pwd)/routing/data:/data \
  osrm/osrm-backend:latest \
  osrm-customize /data/slovakia-latest.osrm

# 3. Run OSRM
docker run -d -p 5000:5000 -v $(pwd)/routing/data:/data \
  osrm/osrm-backend:latest \
  osrm-routed --algorithm mld /data/slovakia-latest.osrm

# 4. Health check
curl http://localhost:5000/health
```

Set `ROUTING_URL=http://localhost:5000` in `.env.local`.

### Isochrones

OSRM does not natively serve isochrones. Use one of:
- `osrm-isochrone` npm package (client-side, Sprint 3)
- Valhalla (built-in `/isochrone` endpoint — see Option B)

## Option B — Valhalla

Valhalla has a built-in isochrone endpoint, which is useful for P-b visualisation.

```bash
# Requires more RAM (~2 GB for SK extract)
docker run -d -p 8002:8002 \
  -v $(pwd)/routing/data:/custom_files \
  -e tile_urls=https://download.geofabrik.de/europe/slovakia-latest.osm.pbf \
  ghcr.io/valhalla/valhalla:latest
```

Set `ROUTING_URL=http://localhost:8002` and update `client.ts` to use Valhalla API format.

## Profiles needed

| Profile | Use case |
|---------|----------|
| `foot` | P-b walking distance (primary) |
| `car` | P-b car time (secondary, for rural areas) |

## Client usage (Sprint 3+)

```ts
import { getRoute, getIsochrone } from "@/services/routing/client";

const route = await getRoute({
  origin: [21.239, 48.999],    // address point [lng, lat]
  destination: [21.241, 49.003], // school [lng, lat]
  profile: "foot",
});
if (route.status !== "ok") {
  // Return INCOMPLETE / LOW_DATA verdict — NEVER straight-line fallback
}
```

## Environment variable

```
ROUTING_URL=http://localhost:5000   # OSRM
# or
ROUTING_URL=http://localhost:8002   # Valhalla
```
