/**
 * Google Maps Directions API client — VLA-17 "5 najdlhších trás" feature.
 *
 * Separate from services/routing/client.ts (OSRM, legacy P-b threshold
 * engine) and from services/transit/index.ts (Google Routes stub reserved
 * for the P-c illustrative indicator). This client backs a different,
 * non-verdict feature: the 5 longest real walking routes per district, plus
 * a transit alternative for addresses in shared/common districts. It carries
 * no threshold or pass/fail logic of its own.
 *
 * CRITICAL: Never substitute straight-line (as-the-crow-flies) distance for
 * a missing route. Always return "low_data" instead — same rule as the OSRM
 * client (see services/routing/client.ts).
 *
 * Env: GOOGLE_API_KEY (server-only, not NEXT_PUBLIC_*).
 */

const DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json";
const GOOGLE_ROUTE_TIMEOUT_MS = 8000; // higher than OSRM's 5s — third-party network tail latency

export type GoogleRouteMode = "walking" | "transit";

export type RoutingStatus = "ok" | "low_data" | "unavailable";

export interface GoogleRouteRequest {
  /** [lng, lat] — same convention as services/routing/client.ts */
  origin: [number, number];
  /** [lng, lat] */
  destination: [number, number];
  mode: GoogleRouteMode;
}

export interface GoogleRouteResult {
  status: RoutingStatus;
  /** Distance in metres; undefined when status !== "ok" */
  distanceMetres?: number;
  /** Duration in seconds; undefined when status !== "ok" */
  durationSeconds?: number;
  /** Google's encoded overview polyline; undefined when status !== "ok" */
  encodedPolyline?: string;
  /** mode "transit" only: short line/vehicle label, e.g. "Autobus 22" */
  transitLine?: string;
}

/**
 * Compute a route between two points using the Google Maps Directions API.
 *
 * IMPORTANT: NEVER fall back to straight-line distance. If the API is
 * unreachable or returns no route, return "low_data" / "unavailable" instead.
 */
export async function getGoogleRoute(request: GoogleRouteRequest): Promise<GoogleRouteResult> {
  const apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    console.warn("GOOGLE_API_KEY not set — routing-google client cannot call the Directions API");
    return { status: "unavailable" };
  }

  const [originLon, originLat] = request.origin;
  const [destLon, destLat] = request.destination;

  const params = new URLSearchParams({
    origin: `${originLat},${originLon}`,
    destination: `${destLat},${destLon}`,
    mode: request.mode,
    key: apiKey,
  });
  const url = `${DIRECTIONS_URL}?${params.toString()}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), GOOGLE_ROUTE_TIMEOUT_MS);

    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);

    if (!res.ok) {
      // Service reachable but HTTP-level failure — not the same as "no route".
      return { status: "unavailable" };
    }

    const data = (await res.json()) as {
      status: string;
      routes?: Array<{
        legs?: Array<{
          distance?: { value: number };
          duration?: { value: number };
          steps?: Array<{
            travel_mode: string;
            transit_details?: { line?: { short_name?: string; name?: string; vehicle?: { name?: string } } };
          }>;
        }>;
        overview_polyline?: { points?: string };
      }>;
    };

    if (data.status === "ZERO_RESULTS") {
      // API reachable, genuinely no route for this pair — do NOT fabricate one.
      return { status: "low_data" };
    }

    if (data.status !== "OK" || !data.routes?.length) {
      // REQUEST_DENIED / INVALID_REQUEST / OVER_QUERY_LIMIT / UNKNOWN_ERROR
      return { status: "unavailable" };
    }

    const route = data.routes[0];
    const leg = route.legs?.[0];
    if (!leg?.distance || !leg?.duration) {
      return { status: "low_data" };
    }

    let transitLine: string | undefined;
    if (request.mode === "transit") {
      const transitStep = leg.steps?.find((s) => s.travel_mode === "TRANSIT" && s.transit_details);
      const line = transitStep?.transit_details?.line;
      if (line) {
        const vehicle = line.vehicle?.name;
        const name = line.short_name ?? line.name;
        transitLine = [vehicle, name].filter(Boolean).join(" ") || undefined;
      }
    }

    return {
      status: "ok",
      distanceMetres: Math.round(leg.distance.value),
      durationSeconds: Math.round(leg.duration.value),
      encodedPolyline: route.overview_polyline?.points,
      transitLine,
    };
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      console.warn(
        `Google Directions timeout for (${originLon},${originLat}) → (${destLon},${destLat}), mode=${request.mode}`
      );
    } else {
      console.warn("Google Directions API unavailable:", err);
    }
    return { status: "unavailable" };
  }
}
