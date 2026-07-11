/**
 * Google Maps Routes API v2 client — VLA-17 "5 najdlhších trás" feature.
 *
 * Separate from services/routing/client.ts (OSRM, legacy P-b threshold
 * engine) and from services/transit/index.ts (Google Routes stub reserved
 * for the P-c illustrative indicator). This client backs a different,
 * non-verdict feature: the 5 longest real walking routes per district, plus
 * a transit alternative for addresses in shared/common districts. It carries
 * no threshold or pass/fail logic of its own.
 *
 * Uses the Routes API v2 computeRoutes endpoint (POST + field mask), NOT the
 * classic Directions API — confirmed live that the classic API is not
 * enabled for this Google Cloud project ("legacy API... not enabled",
 * REQUEST_DENIED), while Routes API v2 works for both WALK and TRANSIT.
 *
 * CRITICAL: Never substitute straight-line (as-the-crow-flies) distance for
 * a missing route. Always return "low_data" instead — same rule as the OSRM
 * client (see services/routing/client.ts).
 *
 * Env: GOOGLE_API_KEY (server-only, not NEXT_PUBLIC_*).
 */

const ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes";
const GOOGLE_ROUTE_TIMEOUT_MS = 8000; // higher than OSRM's 5s — third-party network tail latency
const FIELD_MASK =
  "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline," +
  "routes.legs.steps.travelMode,routes.legs.steps.transitDetails";

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

const TRAVEL_MODE: Record<GoogleRouteMode, "WALK" | "TRANSIT"> = {
  walking: "WALK",
  transit: "TRANSIT",
};

/** Parses "1234s" (Routes API duration string) into whole seconds. */
function parseDurationSeconds(duration: string | undefined): number | undefined {
  if (!duration) return undefined;
  const match = /^(\d+(?:\.\d+)?)s$/.exec(duration);
  if (!match) return undefined;
  return Math.round(parseFloat(match[1]));
}

/**
 * Compute a route between two points using the Google Maps Routes API v2.
 *
 * IMPORTANT: NEVER fall back to straight-line distance. If the API is
 * unreachable or returns no route, return "low_data" / "unavailable" instead.
 */
export async function getGoogleRoute(request: GoogleRouteRequest): Promise<GoogleRouteResult> {
  const apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    console.warn("GOOGLE_API_KEY not set — routing-google client cannot call the Routes API");
    return { status: "unavailable" };
  }

  const [originLon, originLat] = request.origin;
  const [destLon, destLat] = request.destination;

  const body = JSON.stringify({
    origin: { location: { latLng: { latitude: originLat, longitude: originLon } } },
    destination: { location: { latLng: { latitude: destLat, longitude: destLon } } },
    travelMode: TRAVEL_MODE[request.mode],
  });

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), GOOGLE_ROUTE_TIMEOUT_MS);

    const res = await fetch(ROUTES_URL, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": apiKey,
        "X-Goog-FieldMask": FIELD_MASK,
      },
      body,
    });
    clearTimeout(timer);

    if (!res.ok) {
      // computeRoutes returns 200 + empty routes[] for "no route found", and
      // a non-2xx for actual request/auth errors — these are not the same.
      return { status: "unavailable" };
    }

    const data = (await res.json()) as {
      routes?: Array<{
        distanceMeters?: number;
        duration?: string;
        polyline?: { encodedPolyline?: string };
        legs?: Array<{
          steps?: Array<{
            travelMode?: string;
            transitDetails?: {
              transitLine?: { nameShort?: string; name?: string; vehicle?: { name?: { text?: string } } };
            };
          }>;
        }>;
      }>;
    };

    if (!data.routes?.length) {
      // API reachable, genuinely no route for this pair — do NOT fabricate one.
      return { status: "low_data" };
    }

    const route = data.routes[0];
    const durationSeconds = parseDurationSeconds(route.duration);
    if (route.distanceMeters === undefined || durationSeconds === undefined) {
      return { status: "low_data" };
    }

    let transitLine: string | undefined;
    if (request.mode === "transit") {
      const steps = route.legs?.[0]?.steps ?? [];
      const transitStep = steps.find((s) => s.travelMode === "TRANSIT" && s.transitDetails);
      const line = transitStep?.transitDetails?.transitLine;
      if (line) {
        const vehicle = line.vehicle?.name?.text;
        const name = line.nameShort ?? line.name;
        transitLine = [vehicle, name].filter(Boolean).join(" ") || undefined;
      }
    }

    return {
      status: "ok",
      distanceMetres: Math.round(route.distanceMeters),
      durationSeconds,
      encodedPolyline: route.polyline?.encodedPolyline,
      transitLine,
    };
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      console.warn(
        `Google Routes API timeout for (${originLon},${originLat}) → (${destLon},${destLat}), mode=${request.mode}`
      );
    } else {
      console.warn("Google Routes API unavailable:", err);
    }
    return { status: "unavailable" };
  }
}
