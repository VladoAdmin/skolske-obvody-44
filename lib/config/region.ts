// PSK region constants — source of truth for map centering and region identification
export const PSK_BBOX: [number, number, number, number] = [20.4, 48.3, 22.8, 49.7] // minLon, minLat, maxLon, maxLat
export const PSK_CENTER: [number, number] = [49.0, 21.25] // [lat, lon] for Leaflet
export const PSK_DEFAULT_ZOOM = 12
export const PRESOV_MUNICIPALITY_SLUG = 'presov'

// Slovakia overview constants
export const SK_CENTER: [number, number] = [48.74, 19.69] // [lat, lon] for Leaflet
export const SK_DEFAULT_ZOOM = 7

// PSK name variations for GeoJSON matching
export const PSK_KRAJ_NAMES = ['Prešovský samosprávny kraj', 'PSK', 'Prešov', 'Prešovský']

// Composition color map — Tailwind classes + fill opacity
export const COMPOSITION_COLOR_MAP: Record<string, { fill: string; stroke: string; fillOpacity: number; symbol: string }> = {
  GREEN:  { fill: '#16a34a', stroke: '#15803d', fillOpacity: 0.3, symbol: '✓' },
  ORANGE: { fill: '#f97316', stroke: '#ea580c', fillOpacity: 0.3, symbol: '~' },
  RED:    { fill: '#dc2626', stroke: '#b91c1c', fillOpacity: 0.3, symbol: '✕' },
  NONE:   { fill: '#9ca3af', stroke: '#6b7280', fillOpacity: 0.15, symbol: '?' },
}

// Provenance allowlist — mirrors SQL host_in_allowlist() for TS-side safety net
export const PROVENANCE_ALLOWLIST = [
  'slov-lex.sk', 'cvti.sk', 'osm.org', 'openstreetmap.org',
  'geoportal.gov.sk', 'presov.sk', 'gov.sk', 'statistics.sk',
  'atlasromskychkomunit.sk', 'minedu.sk', 'mzv.sk',
] as const

export function isAllowedHost(url: string | null | undefined): boolean {
  if (!url) return false
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    return PROVENANCE_ALLOWLIST.some(
      (allowed) => hostname === allowed || hostname.endsWith('.' + allowed)
    )
  } catch {
    return false
  }
}

// Per-district categorical hue using golden ratio rotation — deterministic, well-distributed
export function getDistrictHue(index: number): number {
  const GOLDEN_RATIO_CONJUGATE = 0.61803398875
  return Math.round(((index * GOLDEN_RATIO_CONJUGATE) % 1) * 360)
}
