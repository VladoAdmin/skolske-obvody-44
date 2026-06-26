/**
 * Transit service adapter — P-c (dopravná dostupnosť)
 *
 * This adapter provides Google Routes API transit lookup for P-c.
 * P-c is ILUSTR. (illustrative) — it never enters the legal compliance verdict.
 *
 * When GOOGLE_MAPS_API_KEY is not set, all calls return NotConfigured status.
 * The engine treats NotConfigured as ILUSTR./NO DATA, never as a legal verdict.
 *
 * Fixed scenario (PRD §11):
 *   - School day (weekday)
 *   - Departure window: 06:30–08:00
 *   - Max 2 transfers
 *   - Return journey included
 *   - Missing route → "dáta nedostupné" (never a guessed verdict)
 */

export type TransitStatus =
  | "ok"
  | "no_data"
  | "not_configured"
  | "error";

export interface TransitRequest {
  /** [lng, lat] */
  origin: [number, number];
  /** [lng, lat] */
  destination: [number, number];
  /** ISO date string for the school day (default: next Monday) */
  departureDate?: string;
}

export interface TransitResult {
  status: TransitStatus;
  /** Total journey time in minutes (one-way), if found */
  totalMinutes?: number;
  /** Number of transfers */
  transfers?: number;
  /** Illustrative notice — always shown when P-c is used */
  disclaimer: string;
}

const DISCLAIMER =
  "P-c: Ilustračný náhľad dopravy (Google Routes API). " +
  "Nevstupuje do zákonného stavu súladu. " +
  "Bez agentúrneho GTFS; scenár: školský deň 06:30–08:00, max 2 prestupy.";

/**
 * Look up transit route for P-c assessment.
 * Returns NotConfigured when GOOGLE_MAPS_API_KEY is absent.
 * NEVER returns a verdict — this is illustrative only.
 */
export async function getTransitRoute(
  request: TransitRequest
): Promise<TransitResult> {
  const apiKey = process.env.GOOGLE_MAPS_API_KEY;

  if (!apiKey) {
    return {
      status: "not_configured",
      disclaimer: DISCLAIMER,
    };
  }

  // TODO Sprint 2: implement Google Routes API computeRoutes call
  // with travelMode=TRANSIT, transitPreferences, departureTime in 06:30-08:00 window.
  // Cache result in DB (low API cost per PLAN).
  void request;

  return {
    status: "no_data",
    disclaimer: DISCLAIMER,
  };
}

/**
 * Check if transit data is available for a given origin/destination.
 * Used to gate P-c display in the UI.
 */
export function isTransitConfigured(): boolean {
  return Boolean(process.env.GOOGLE_MAPS_API_KEY);
}
