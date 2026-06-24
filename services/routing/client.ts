/**
 * Routing service client — Sprint 1 implementation.
 *
 * Wraps OSRM (walking profile) for:
 *   - Walking distance / travel time (P-b, Š threshold checks)
 *   - Isochrone generation (P-b visualisation)
 *
 * G-ROUTING gate (PLAN §0.5):
 *   - OSRM deployed and reachable (see routing/docker-compose.yml)
 *   - Walking profile confirmed working
 *   - Address snapping test passes
 *   - Fallback LOW_DATA returned when route unavailable (NEVER straight-line)
 *
 * CRITICAL: Never substitute straight-line (as-the-crow-flies) distance
 * for a missing route. Always return LOW_DATA status instead.
 */

const ROUTING_URL = process.env.ROUTING_URL ?? "http://localhost:5000";
const ROUTING_TIMEOUT_MS = 5000; // 5 seconds per route request

export type RouteProfile = "foot" | "car";

export interface RouteRequest {
  /** [lng, lat] */
  origin: [number, number];
  /** [lng, lat] */
  destination: [number, number];
  profile: RouteProfile;
}

export type RoutingStatus = "ok" | "low_data" | "unavailable";

export interface RouteResult {
  status: RoutingStatus;
  /** Distance in metres; undefined when status !== "ok" */
  distanceMetres?: number;
  /** Duration in seconds; undefined when status !== "ok" */
  durationSeconds?: number;
}

export interface IsochroneRequest {
  /** [lng, lat] */
  center: [number, number];
  profile: RouteProfile;
  /** Contour distances in metres */
  contours: number[];
}

export interface IsochroneResult {
  status: RoutingStatus;
  /** GeoJSON FeatureCollection of isochrone polygons; undefined when status !== "ok" */
  geojson?: unknown;
}

/**
 * Check if the routing service is reachable.
 * Returns true if healthy, false otherwise.
 */
export async function isRoutingAvailable(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${ROUTING_URL}/health`, { signal: controller.signal });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Compute walking route between two points using OSRM.
 *
 * IMPORTANT: NEVER fall back to straight-line distance.
 * If the service is unavailable or the route is not found, return LOW_DATA.
 *
 * OSRM endpoint: GET /route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}
 * Uses MLD algorithm (fastest for large graphs).
 */
export async function getRoute(request: RouteRequest): Promise<RouteResult> {
  const [originLon, originLat] = request.origin;
  const [destLon, destLat] = request.destination;
  const profile = request.profile === "foot" ? "foot" : "driving";

  const url = `${ROUTING_URL}/route/v1/${profile}/${originLon},${originLat};${destLon},${destLat}?overview=false&steps=false`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ROUTING_TIMEOUT_MS);

    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);

    if (!res.ok) {
      // Service reachable but route failed (e.g., no road access)
      return { status: "low_data" };
    }

    const data = await res.json() as {
      code: string;
      routes?: Array<{ distance: number; duration: number }>;
    };

    if (data.code !== "Ok" || !data.routes?.length) {
      // OSRM returned no route — do NOT fall back to straight-line
      return { status: "low_data" };
    }

    return {
      status: "ok",
      distanceMetres: Math.round(data.routes[0].distance),
      durationSeconds: Math.round(data.routes[0].duration),
    };
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      console.warn(`Routing timeout for (${originLon},${originLat}) → (${destLon},${destLat})`);
    } else {
      console.warn("Routing service unavailable:", err);
    }
    return { status: "unavailable" };
  }
}

/**
 * Generate isochrone polygons around a point using OSRM table API.
 *
 * Note: OSRM doesn't have a native isochrone endpoint. We approximate
 * by calling the table API with sample grid points and filtering by
 * travel time. For Sprint 1 this returns unavailable — Sprint 3 implements
 * the full isochrone via Valhalla or a custom OSRM wrapper.
 *
 * IMPORTANT: NEVER return straight-line-based isochrones.
 */
export async function getIsochrone(
  request: IsochroneRequest
): Promise<IsochroneResult> {
  // Sprint 1: stub — real implementation in Sprint 3 via Valhalla isochrone API
  // or osrm-isochrone library.
  // Returning unavailable is correct: caller treats as LOW_DATA, not as a fake polygon.
  void request;
  return { status: "unavailable" };
}

/**
 * Smoke test: verify OSRM is running and can route within Prešov.
 * Uses two known PSK addresses near Prešov city centre.
 * Returns test result details.
 */
export async function smokTestRouting(): Promise<{
  available: boolean;
  sampleRoute?: RouteResult;
  latencyMs?: number;
}> {
  const available = await isRoutingAvailable();
  if (!available) {
    return { available: false };
  }

  // Prešov: ZŠ Bajkalská → ZŠ Kúpeľná (roughly 2 km walking)
  const start = Date.now();
  const sampleRoute = await getRoute({
    origin: [21.2611, 49.0014],   // ZŠ Bajkalská area
    destination: [21.2400, 49.0200], // ZŠ Kúpeľná area
    profile: "foot",
  });
  const latencyMs = Date.now() - start;

  return { available: true, sampleRoute, latencyMs };
}
