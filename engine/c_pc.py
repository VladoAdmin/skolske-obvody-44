"""
P-c — Dopravná dostupnosť (Transit availability — ILLUSTRATIVE via Google Routes API).

METHODOLOGY §P-c:
  Illustrative only. Never enters legal status.
  Fixed scenario: school morning, departure next Monday 07:30 local, max 2 transfers.
  Origin = district centroid. Destination = assigned school.

  Value:
    ILUSTRATIVE_AVAILABLE = transit route found
    ILUSTR_NO_DATA        = no transit data / API not available / no key

  Gatekeeping: is_illustrative=True; NEVER included in semafor composition.

P-c is only called for districts where P-b = RISK or FAIL
(per spec "For districts where P-b is RISK/FAIL").
For P-b = PASS districts, P-c still runs but result is purely supplemental.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY", ""))
GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

_METHODOLOGY = {
    "rule": "Pc-transit-google-routes",
    "version": METHODOLOGY_VERSION,
    "scenario": "school morning, next Monday 07:30 local, max 2 transfers",
    "api": "Google Routes API computeRoutes travelMode=TRANSIT",
    "law_ref": "§44 ods. 8 písm. c)",
    "never_claims": (
        "doprava spĺňa/nespĺňa zákon — ilustračný náhľad bez agentúrneho GTFS; "
        "nevstupuje do zákonného stavu"
    ),
    "gatekeeping": "is_illustrative=True — nikdy do semafor kompozície",
}


def _next_monday_0730_utc() -> str:
    """ISO8601 timestamp for next Monday 07:30 Bratislava time (UTC+2 summer)."""
    now = datetime.now(timezone.utc)
    days_ahead = (7 - now.weekday()) % 7  # days until Monday
    if days_ahead == 0:
        days_ahead = 7
    next_mon = now + timedelta(days=days_ahead)
    # 07:30 Bratislava = 05:30 UTC in summer (CEST = UTC+2)
    departure = next_mon.replace(hour=5, minute=30, second=0, microsecond=0)
    return departure.strftime("%Y-%m-%dT%H:%M:%SZ")


def _call_google_routes(
    origin_lon: float, origin_lat: float,
    dest_lon: float, dest_lat: float,
) -> dict:
    """Call Google Routes API. Returns summary dict."""
    if not GOOGLE_API_KEY:
        return {"status": "NO_API_KEY", "error": "GOOGLE_API_KEY not set in environment"}

    departure_time = _next_monday_0730_utc()
    payload = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lon}}},
        "travelMode": "TRANSIT",
        "departureTime": departure_time,
        "transitPreferences": {
            "allowedTravelModes": ["BUS", "RAIL", "SUBWAY"],
            "routingPreference": "LESS_WALKING",
        },
        "computeAlternativeRoutes": False,
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "routes.duration,routes.distanceMeters,"
            "routes.legs.steps.transitDetails"
        ),
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(GOOGLE_ROUTES_URL, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        routes = result.get("routes", [])
        if not routes:
            return {"status": "ZERO_RESULTS", "raw": result}
        route = routes[0]
        return {
            "status": "OK",
            "duration_s": route.get("duration", ""),
            "distance_m": route.get("distanceMeters"),
            "departure_time": departure_time,
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"status": f"HTTP_{e.code}", "error": body[:200]}
    except Exception as ex:
        return {"status": "ERROR", "error": str(ex)[:200]}


def check_pc(district: dict) -> Verdict:
    district_id = district["id"]
    school_id = district.get("school_id")

    if not school_id:
        return _no_data_verdict(district_id, "school_id IS NULL")

    # Get centroid
    centroid_rows = query_sql(f"""
        SELECT public.ST_X(public.ST_Centroid(geom)) as lon,
               public.ST_Y(public.ST_Centroid(geom)) as lat
        FROM skolske_obvody.districts
        WHERE id = '{district_id}'
    """)
    if not centroid_rows:
        return _no_data_verdict(district_id, "district centroid unavailable")

    origin_lon = float(centroid_rows[0]["lon"])
    origin_lat = float(centroid_rows[0]["lat"])

    # Get school location
    school_rows = query_sql(f"""
        SELECT public.ST_X(geom) as lon, public.ST_Y(geom) as lat, name
        FROM skolske_obvody.schools WHERE id = '{school_id}'
    """)
    if not school_rows or not school_rows[0].get("lon"):
        return _no_data_verdict(district_id, "school geom NULL")

    dest_lon = float(school_rows[0]["lon"])
    dest_lat = float(school_rows[0]["lat"])
    school_name = school_rows[0].get("name", "")

    transit_result = _call_google_routes(origin_lon, origin_lat, dest_lon, dest_lat)

    if transit_result.get("status") == "OK":
        value = V.ILUSTRATIVE_AVAILABLE
        evidence = (
            f"ILUSTR. DOSTUPNÉ: tranzitná trasa nájdená. "
            f"Škola: {school_name}. "
            f"Čas odchodu: {transit_result.get('departure_time')}. "
            "Ilustračné — nevstupuje do zákonného stavu."
        )
    else:
        value = V.ILUSTR_NO_DATA
        evidence = (
            f"ILUSTR. BEZ DÁT: status = {transit_result.get('status')}. "
            f"Škola: {school_name}. "
            "Ilustračné — nevstupuje do zákonného stavu."
        )

    provenance = {
        "source": "Google Routes API (TRANSIT)",
        "scenario": "school morning next Monday 07:30",
        "max_transfers": 2,
        "origin": {"lon": origin_lon, "lat": origin_lat, "type": "district_centroid"},
        "destination": {"school_id": school_id, "school_name": school_name},
        "api_result": transit_result,
    }

    return Verdict(
        district_id=district_id,
        condition_code="Pc",
        value=value,
        confidence=0.5 if transit_result.get("status") == "OK" else 0.0,
        data_completeness=0.3,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
        is_illustrative=True,
    )


def _no_data_verdict(district_id: str, reason: str) -> Verdict:
    return Verdict(
        district_id=district_id,
        condition_code="Pc",
        value=V.ILUSTR_NO_DATA,
        confidence=0.0,
        data_completeness=0.0,
        provenance={"reason": reason},
        methodology=_METHODOLOGY,
        evidence_text=f"ILUSTR. BEZ DÁT: {reason}. Nevstupuje do zákonného stavu.",
        is_illustrative=True,
    )
