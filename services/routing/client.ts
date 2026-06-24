/**
 * Routing service client — Sprint 0 stub.
 *
 * Wraps OSRM or Valhalla for:
 *   - Walking distance / travel time (P-b, Š threshold checks)
 *   - Isochrone generation (P-b visualisation)
 *
 * Sprint 3 wires the real implementation.
 * Gate G-ROUTING (from PLAN §0.5) must pass before P-b is computed:
 *   - OSRM/Valhalla deployed and reachable
 *   - Walking profile confirmed working
 *   - Address snapping test passes
 *   - Fallback LOW_DATA returned when route unavailable (NEVER straight-line)
 */

const ROUTING_URL = process.env.ROUTING_URL ?? "http://localhost:5000";

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
 * Stub: compute route between two points.
 * Sprint 3: replace with real OSRM /route or Valhalla /route endpoint call.
 * IMPORTANT: NEVER fall back to straight-line distance — return LOW_DATA instead.
 */
export async function getRoute(request: RouteRequest): Promise<RouteResult> {
  // TODO Sprint 3: implement real routing call
  void request;
  void ROUTING_URL;
  return { status: "unavailable" };
}

/**
 * Stub: generate isochrone polygons around a point.
 * Sprint 3: replace with OSRM isochrone or Valhalla /isochrone endpoint.
 */
export async function getIsochrone(
  request: IsochroneRequest
): Promise<IsochroneResult> {
  // TODO Sprint 3: implement real isochrone call
  void request;
  return { status: "unavailable" };
}
