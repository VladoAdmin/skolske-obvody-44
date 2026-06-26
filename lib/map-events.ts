/**
 * Type-safe contracts for custom window events used by the map components.
 *
 * Import the EVENT_* constants everywhere you dispatch or listen so that a
 * typo becomes a compile-time error rather than a silent no-op at runtime.
 */

// ---------------------------------------------------------------------------
// Event name constants
// ---------------------------------------------------------------------------

/** Fly the map viewport to a lat/lon position. */
export const EVENT_FLYTO = 'so:flyto' as const

/** Select (highlight + flyTo bounds) a district polygon on the region map. */
export const EVENT_SELECT_DISTRICT = 'so:select-district' as const

/** Toggle a single district polygon's visibility on the region map. */
export const EVENT_TOGGLE_DISTRICT = 'so:toggle-district' as const

/** Draw an air-line route on the region map for a distance finding (Pa/Pb). */
export const EVENT_DRAW_ROUTE = 'so:draw-route' as const

// ---------------------------------------------------------------------------
// Event detail types
// ---------------------------------------------------------------------------

export interface FlyToDetail {
  lat: number
  lon: number
  zoom?: number
}

export interface SelectDistrictDetail {
  id: string
}

export interface ToggleDistrictDetail {
  id: string
  visible: boolean
}

export interface DrawRouteDetail {
  districtId: string
  from: { lat: number; lon: number }
  to: { lat: number; lon: number }
  label?: string
}
