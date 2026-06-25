// PSK region constants — source of truth for map centering and region identification
export const PSK_BBOX: [number, number, number, number] = [20.4, 48.3, 22.8, 49.7] // minLon, minLat, maxLon, maxLat
export const PSK_CENTER: [number, number] = [49.0, 21.6] // [lat, lon] for Leaflet
export const PSK_DEFAULT_ZOOM = 9
export const PRESOV_MUNICIPALITY_SLUG = 'presov'

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
