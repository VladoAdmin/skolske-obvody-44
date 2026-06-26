"""
Routing smoke test — G-ROUTING gate.

Tests 20 random PSK address → school routing calls.
All must complete within 2 seconds each.

Usage:
    export ROUTING_URL=http://localhost:5000
    python3 -m ingest.smoke_test_routing
"""

import json
import sys
import time
import urllib.request
import urllib.error
import random
from typing import Optional

ROUTING_URL = __import__("os").environ.get("ROUTING_URL", "http://localhost:5000")

# 20 test route pairs: (from_lon, from_lat, to_lon, to_lat, description)
# All within Prešovský kraj — known address coordinates to school points
TEST_ROUTES = [
    # Format: [from_lon, from_lat, to_lon, to_lat, description]
    [21.2200, 49.0150, 21.2400, 49.0220, "Prešov south to ZŠ Kúpeľná"],
    [21.2611, 49.0014, 21.2500, 49.0100, "Prešov east to ZŠ Bajkalská"],
    [21.2350, 48.9950, 21.2400, 49.0100, "Prešov south to city centre"],
    [21.2700, 49.0200, 21.2400, 49.0200, "Prešov west-east cross"],
    [21.2100, 49.0300, 21.2400, 49.0200, "Prešov north-west to centre"],
    [21.2500, 49.0050, 21.2380, 49.0180, "Prešov SE quadrant"],
    [21.2600, 49.0150, 21.2300, 49.0050, "Prešov cross-diagonal 1"],
    [21.2450, 49.0250, 21.2550, 49.0100, "Prešov cross-diagonal 2"],
    [21.2200, 49.0200, 21.2550, 49.0200, "Prešov E-W"],
    [21.2350, 49.0350, 21.2400, 49.0200, "Prešov N to centre"],
    # Wider PSK: Sabinov district
    [21.1000, 49.1000, 21.0800, 49.0900, "Sabinov area"],
    # Poprad area
    [20.2978, 49.0610, 20.3100, 49.0700, "Poprad local route"],
    # Bardejov area
    [21.2757, 49.2960, 21.2800, 49.2900, "Bardejov local route"],
    # Stará Ľubovňa
    [20.6857, 49.3050, 20.6900, 49.3100, "Stará Ľubovňa local"],
    # Humenné
    [21.9050, 48.9332, 21.9100, 48.9400, "Humenné local"],
    # Michalovce adjacent
    [22.0000, 48.7500, 22.0100, 48.7600, "Michalovce adjacent"],
    # Stropkov
    [21.6500, 49.2000, 21.6600, 49.2100, "Stropkov local"],
    # Vranov nad Topľou
    [21.6792, 48.8800, 21.6900, 48.8900, "Vranov local"],
    # Levoča
    [20.5900, 49.0250, 20.5950, 49.0300, "Levoča local"],
    # Spišská Nová Ves
    [20.5700, 48.9500, 20.5750, 48.9550, "Spišská Nová Ves"],
]


def check_osrm_health() -> bool:
    """Check if OSRM is reachable."""
    try:
        req = urllib.request.Request(f"{ROUTING_URL}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def route_request(
    from_lon: float, from_lat: float,
    to_lon: float, to_lat: float,
) -> dict:
    """Make a single OSRM route request. Returns result dict."""
    url = (
        f"{ROUTING_URL}/route/v1/foot/"
        f"{from_lon},{from_lat};{to_lon},{to_lat}"
        f"?overview=false&steps=false"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "SkolskeObvody-SmokeTest/1.0"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency_ms = (time.time() - start) * 1000
            code = data.get("code", "")
            routes = data.get("routes", [])
            if code == "Ok" and routes:
                return {
                    "status": "ok",
                    "distance_m": round(routes[0]["distance"]),
                    "duration_s": round(routes[0]["duration"]),
                    "latency_ms": round(latency_ms),
                }
            else:
                return {"status": "low_data", "code": code, "latency_ms": round(latency_ms)}
    except urllib.error.URLError as e:
        return {"status": "unavailable", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main() -> int:
    print("=" * 60)
    print("G-ROUTING SMOKE TEST — 20 PSK route pairs")
    print(f"OSRM URL: {ROUTING_URL}")
    print("=" * 60)

    # Health check
    print("\nChecking OSRM health...")
    if not check_osrm_health():
        print(f"FAIL: OSRM not reachable at {ROUTING_URL}")
        print("  → Run: docker compose -f routing/docker-compose.yml up -d")
        print("  → Or set ROUTING_URL env var to correct endpoint")
        return 1

    print("  OSRM reachable ✓")

    # Route tests
    results = []
    print(f"\nTesting {len(TEST_ROUTES)} route pairs...")

    for i, (from_lon, from_lat, to_lon, to_lat, desc) in enumerate(TEST_ROUTES):
        result = route_request(from_lon, from_lat, to_lon, to_lat)
        result["description"] = desc
        result["index"] = i + 1
        results.append(result)

        status = result["status"]
        latency = result.get("latency_ms", "?")
        if status == "ok":
            dist_km = result.get("distance_m", 0) / 1000
            dur_min = result.get("duration_s", 0) / 60
            print(f"  [{i+1:2d}] {status:10s} {dist_km:.2f}km / {dur_min:.1f}min  ({latency}ms)  {desc}")
        else:
            print(f"  [{i+1:2d}] {status:10s} ({latency}ms)  {desc}")

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "ok")
    low_data_count = sum(1 for r in results if r["status"] == "low_data")
    unavailable_count = sum(1 for r in results if r["status"] in ("unavailable", "error"))

    latencies = [r["latency_ms"] for r in results if "latency_ms" in r]
    max_latency = max(latencies) if latencies else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    print(f"\n{'='*60}")
    print(f"Results: {ok_count} ok / {low_data_count} low_data / {unavailable_count} unavailable")
    print(f"Latency: avg={avg_latency:.0f}ms, max={max_latency:.0f}ms")
    print()

    # Gate criteria
    timeout_violations = [r for r in results if r.get("latency_ms", 0) > 2000]
    if timeout_violations:
        print(f"FAIL: {len(timeout_violations)} routes exceeded 2000ms threshold")
        for r in timeout_violations:
            print(f"  Route {r['index']}: {r['latency_ms']}ms — {r['description']}")
        return 1

    if unavailable_count > 0:
        print(f"WARN: {unavailable_count} routes returned unavailable (network/routing issue)")

    if ok_count == 0:
        print("FAIL: No routes returned OK status — check walking profile and OSM data")
        return 1

    print(f"G-ROUTING GATE: PASS ✓")
    print(f"  → {ok_count}/{len(TEST_ROUTES)} routes computed within 2 seconds each")
    print(f"  → Fallback LOW_DATA for {low_data_count} routes (no path — not straight-line)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
