#!/bin/bash
# OSRM Setup Script — Slovakia walking profile
# Run once before starting docker-compose.
#
# Requirements: docker, ~2GB disk for Slovakia OSM extract + OSRM graph
# Time: ~5-10 minutes for preprocessing

set -euo pipefail

DATA_DIR="$(dirname "$0")/data"
OSM_FILE="slovakia-latest.osm.pbf"
OSM_URL="https://download.geofabrik.de/europe/slovakia-latest.osm.pbf"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

# 1. Download Slovakia OSM extract from Geofabrik
if [ ! -f "$OSM_FILE" ]; then
    echo "Downloading Slovakia OSM extract from Geofabrik (~150MB)..."
    curl -L --retry 3 --retry-delay 5 -o "$OSM_FILE" "$OSM_URL"
    echo "Downloaded: $(du -sh $OSM_FILE)"
else
    echo "OSM extract already exists: $OSM_FILE"
fi

# 2. Extract (foot profile for walking)
echo "Extracting with foot profile..."
docker run --rm \
    -v "$(pwd):/data" \
    ghcr.io/project-osrm/osrm-backend:latest \
    osrm-extract \
    -p /opt/car.lua \
    /data/"$OSM_FILE" \
    -i /opt/profiles/foot.lua 2>/dev/null || \
docker run --rm \
    -v "$(pwd):/data" \
    ghcr.io/project-osrm/osrm-backend:latest \
    osrm-extract \
    /data/"$OSM_FILE" \
    -p /opt/profiles/foot.lua

# 3. Partition
echo "Partitioning..."
docker run --rm \
    -v "$(pwd):/data" \
    ghcr.io/project-osrm/osrm-backend:latest \
    osrm-partition /data/slovakia-latest.osrm

# 4. Customize
echo "Customizing..."
docker run --rm \
    -v "$(pwd):/data" \
    ghcr.io/project-osrm/osrm-backend:latest \
    osrm-customize /data/slovakia-latest.osrm

echo ""
echo "OSRM setup complete!"
echo "Start the routing service with:"
echo "  docker compose -f routing/docker-compose.yml up -d"
echo ""
echo "Smoke test:"
echo "  curl 'http://localhost:5000/route/v1/foot/21.2611,49.0014;21.2400,49.0200?overview=false'"
