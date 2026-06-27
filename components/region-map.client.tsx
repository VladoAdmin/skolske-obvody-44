'use client'

import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoDistrictIsland, SoPskMunicipality, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi, SoDistrictCleanGeom, SoHouseDot } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, SK_CENTER, SK_DEFAULT_ZOOM, PSK_KRAJ_NAMES, COMPOSITION_COLOR_MAP, getDistrictHue } from '@/lib/config/region'
import { buildDistrictSchoolPopup, buildDistrictSummaryPopup, buildNonVznSchoolPopup, type DistrictPopupSummary } from '@/lib/compliance/school-popup'
import {
  EVENT_FLYTO,
  EVENT_SELECT_DISTRICT,
  EVENT_TOGGLE_DISTRICT,
  EVENT_DRAW_ROUTE,
  type FlyToDetail,
  type SelectDistrictDetail,
  type ToggleDistrictDetail,
  type DrawRouteDetail,
} from '@/lib/map-events'

// Zoom threshold (inclusive) at which per-house dots become visible.
const HOUSE_DOTS_MIN_ZOOM = 16

// --- DEMO illustration scenario (Sprint demo-mode) -------------------------
// The two RED demo districts whose § 44 findings the map must visually
// illustrate the moment the user taps the polygon. IDs are the same UUIDs the
// demo-mode verdict seed + demo_overlap_island.sql key their geometry on, so
// the overlap/island demo polygons already arrive client-side via the
// `overlaps` / `islands` props (is_demo = true) and we just need to surface the
// relevant ones on click.
const DEMO_DISTRICT_SMERALOVA = 'cddfee4e-fb1d-48c1-bbb5-2626ae415f87'
const DEMO_DISTRICT_NESPORA = '022b88de-8f54-43fd-9a37-b165102db9f8'
const DEMO_RED_DISTRICT_IDS = new Set<string>([
  DEMO_DISTRICT_SMERALOVA,
  DEMO_DISTRICT_NESPORA,
])

// Haversine straight-line distance in metres between two [lat, lon] points.
function haversineMeters(a: [number, number], b: [number, number]): number {
  const R = 6371000
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b[0] - a[0])
  const dLon = toRad(b[1] - a[1])
  const lat1 = toRad(a[0])
  const lat2 = toRad(b[0])
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

// Walk every coordinate of a (Multi)Polygon GeoJSON and return the vertex
// ([lat, lon]) farthest (great-circle) from the given school point. Used to
// derive the Pa "long distance" illustration line geometrically from the
// existing district polygon — no extra DB columns needed.
function farthestVertexFromSchool(
  geom: Record<string, unknown> | null | undefined,
  school: [number, number]
): { point: [number, number]; meters: number } | null {
  if (!geom) return null
  const type = geom.type as string | undefined
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const coords = geom.coordinates as any
  if (!coords) return null

  let best: [number, number] | null = null
  let bestM = -1
  const consider = (lon: number, lat: number) => {
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return
    const d = haversineMeters(school, [lat, lon])
    if (d > bestM) {
      bestM = d
      best = [lat, lon]
    }
  }
  // GeoJSON Polygon: coordinates = ring[][]; MultiPolygon: poly[ring[][]]
  const rings: number[][][] =
    type === 'MultiPolygon' ? coords.flat() : type === 'Polygon' ? coords : []
  for (const ring of rings) {
    for (const pt of ring) {
      consider(pt[0], pt[1])
    }
  }
  if (!best) return null
  return { point: best, meters: bestM }
}

// On small screens the Leaflet layer-toggle control must start COLLAPSED so it
// does not obscure the map; it expands into the full checkbox list on tap.
// On desktop it stays open (collapsed: false) as before.
function layerControlCollapsed(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(max-width: 767px)').matches
}

interface RegionMapClientProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  findings: SoFindingsPanelItem[]
  overlaps?: SoDistrictOverlap[]
  islands?: SoDistrictIsland[]
  municipalities?: SoPskMunicipality[]
  streetGeocodes?: SoStreetGeocode[]
  housePoints?: SoHousePoint[]
  voronoiGeom?: SoDistrictVoronoi[]
  cleanGeom?: SoDistrictCleanGeom[]
  houseDots?: SoHouseDot[]
  districtSummaries?: Record<string, DistrictPopupSummary>
  initialMode?: 'sk' | 'psk'
}

function isPskKraj(name: string): boolean {
  const lower = name.toLowerCase()
  return PSK_KRAJ_NAMES.some((n) => lower.includes(n.toLowerCase()))
}

export function RegionMapClient({ features, schools, mrkOverlays, overlaps = [], islands = [], municipalities = [], streetGeocodes = [], housePoints = [], voronoiGeom = [], cleanGeom = [], houseDots = [], districtSummaries = {}, initialMode = 'sk' }: RegionMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layersRef = useRef<{ sk?: any; psk?: any }>({})
  // Per-district layer map: id -> L.GeoJSON layer
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const districtLayersRef = useRef<Map<string, any>>(new Map())
  // Active route polyline drawn for distance findings (Pa/Pb). Held in a ref
  // so successive events remove the previous line before drawing a new one,
  // and the effect cleanup can remove it on unmount.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const routeLayerRef = useRef<any>(null)
  // DEMO illustration layer group (island/overlap/long-distance) shown only
  // while one of the two RED demo districts is selected. Cleared on any other
  // selection / empty-map tap so the other 10 districts are unaffected.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const demoIllustrationRef = useRef<any>(null)
  // DOM node of the demo legend box (created lazily, toggled with the layer).
  const demoLegendRef = useRef<HTMLDivElement | null>(null)
  // Bridge so the init-effect's EVENT_SELECT_DISTRICT handler can trigger the
  // demo illustration that is built inside the (separate) mode effect closure.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const drawDemoRef = useRef<((feature: any) => void) | null>(null)
  // Currently click-selected district id (for highlight reset on next tap /
  // popup close / empty-map tap). Mirrors the visual "selected" style.
  const selectedDistrictIdRef = useRef<string | null>(null)
  const [mode, setMode] = useState<'sk' | 'psk'>(initialMode)
  const [mapReady, setMapReady] = useState(false)
  const modeRef = useRef(mode)

  // keep modeRef in sync for use inside closure
  useEffect(() => {
    modeRef.current = mode
  }, [mode, mapReady])

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    import('leaflet').then((L) => {
      if (!containerRef.current || mapRef.current) return

      // Fix default icon paths for Next.js bundling
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-shadow.png',
      })

      const map = L.map(containerRef.current!, {
        center: SK_CENTER,
        zoom: SK_DEFAULT_ZOOM,
        worldCopyJump: false,
        maxBounds: [[47.2, 16.5], [49.9, 22.8]] as [[number, number], [number, number]],
        maxBoundsViscosity: 1.0,
        minZoom: 7,
      })

      mapRef.current = map

      // Create z-ordering panes
      // MRK pane sits BELOW districts so that, even when the MRK overlay is
      // toggled on, tapping a district area hits the district polygon (and its
      // summary popup) rather than the MRK hatch underneath it.
      const mrkPane = map.createPane('mrk')
      mrkPane.style.zIndex = '440'
      const districtPane = map.createPane('districts')
      districtPane.style.zIndex = '450'
      const overlapsPane = map.createPane('overlaps')
      overlapsPane.style.zIndex = '470'
      // Apply multiply blend mode so stacked overlap polygons darken additively
      overlapsPane.style.mixBlendMode = 'multiply'
      const schoolsPane = map.createPane('schools')
      schoolsPane.style.zIndex = '700'
      const streetPointsPane = map.createPane('streetPoints')
      streetPointsPane.style.zIndex = '680'

      // The district/school SUMMARY popup must always sit ABOVE the school point
      // markers. Leaflet's default popupPane and our custom `schools` pane are
      // both at zIndex 700, so with equal z the later-painted school markers
      // covered the open summary table. Lift the popup pane clear of the markers.
      const popupPane = map.getPane('popupPane')
      if (popupPane) popupPane.style.zIndex = '750'

      // Inject MRK hatch pattern SVG once
      if (!document.getElementById('mrkHatchDefs')) {
        const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        svgEl.setAttribute('id', 'mrkHatchDefs')
        svgEl.setAttribute('width', '0')
        svgEl.setAttribute('height', '0')
        svgEl.style.position = 'absolute'
        svgEl.innerHTML = `<defs><pattern id="mrkHatch" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#7c3aed" stroke-width="3" stroke-opacity="0.5" /></pattern></defs>`
        document.body.appendChild(svgEl)
      }

      setMapReady(true)

      // OSM tile layer with mandatory attribution
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom: 19,
        noWrap: true,
        bounds: [[47.2, 16.5], [49.9, 22.8]] as unknown as [[number, number], [number, number]],
      }).addTo(map)

      // --- CustomEvent listener for flyTo from findings panel ---
      const flyToHandler = (e: Event) => {
        const { lat, lon, zoom } = (e as CustomEvent<FlyToDetail>).detail
        map.flyTo([lat, lon], zoom ?? 15, { duration: 1 })
      }
      window.addEventListener(EVENT_FLYTO, flyToHandler)

      // --- CustomEvent: toggle individual district visibility ---
      const toggleDistrictHandler = (e: Event) => {
        const { id, visible } = (e as CustomEvent<ToggleDistrictDetail>).detail
        const layer = districtLayersRef.current.get(id)
        if (!layer) return
        if (visible) {
          map.addLayer(layer)
        } else {
          map.removeLayer(layer)
        }
      }
      window.addEventListener(EVENT_TOGGLE_DISTRICT, toggleDistrictHandler)

      // --- CustomEvent: select district (highlight + flyTo centroid) ---
      const selectDistrictHandler = (e: Event) => {
        const { id } = (e as CustomEvent<SelectDistrictDetail>).detail
        districtLayersRef.current.forEach((layer, layerId) => {
          const featureIndex = features.findIndex((f) => f.id === layerId)
          const hue = getDistrictHue(featureIndex >= 0 ? featureIndex : 0)
          if (layerId === id) {
            layer.setStyle({ weight: 4.5, fillOpacity: 0.55, fillColor: `hsl(${hue}, 65%, 55%)` })
            layer.bringToFront()
            selectedDistrictIdRef.current = id
            try {
              const bounds = layer.getBounds()
              if (bounds.isValid()) {
                map.flyToBounds(bounds, { padding: [30, 30], duration: 1 })
              }
            } catch { /* ignore */ }
            // Surface the geometric § 44 illustration (island / overlap /
            // long-distance) for the selected district so picking a finding from
            // the panel focuses the same visual evidence as tapping the polygon.
            const feature = features.find((f) => f.id === id)
            if (feature && drawDemoRef.current) {
              drawDemoRef.current(feature)
            }
            // Open the district summary popup so the detail is surfaced on the map.
            try { layer.openPopup() } catch { /* ignore */ }
          } else {
            // restore the solid-fill default (distinct palette colour)
            layer.setStyle({ weight: 2.5, fillOpacity: 0.40 })
          }
        })
      }
      window.addEventListener(EVENT_SELECT_DISTRICT, selectDistrictHandler)

      // --- CustomEvent: draw a route line for distance findings (Pa/Pb) ---
      // Draws a dashed line from the district centroid (representative address
      // area) to the school location so the user can see the problematic
      // air-line distance visually. Replaces any previous route layer.
      const drawRouteHandler = (e: Event) => {
        const { from, to, label } = (e as CustomEvent<DrawRouteDetail>).detail
        // Validate coordinates — skip if any coordinate is non-finite
        if (
          !Number.isFinite(from.lat) || !Number.isFinite(from.lon) ||
          !Number.isFinite(to.lat)   || !Number.isFinite(to.lon)
        ) return
        // Remove previous route if any
        if (routeLayerRef.current) {
          map.removeLayer(routeLayerRef.current)
          routeLayerRef.current = null
        }
        const fromLatLng: [number, number] = [from.lat, from.lon]
        const toLatLng: [number, number] = [to.lat, to.lon]
        // Compute straight-line distance in metres (Haversine via Leaflet)
        const distM = map.distance(fromLatLng, toLatLng)
        const distKm = (distM / 1000).toFixed(2)
        routeLayerRef.current = L.polyline([fromLatLng, toLatLng], {
          color: '#dc2626',    // red-600 — problem highlight
          weight: 3,
          dashArray: '8,5',
          opacity: 0.85,
        })
          .bindPopup(
            `<strong>${label ?? 'Vzdialenosť'}</strong><br/>` +
            `Vzdušná vzdialenosť: <strong>${distKm} km</strong><br/>` +
            `<em>Centroid obvodu → škola</em>`,
            { maxWidth: 220 }
          )
          .addTo(map)
        routeLayerRef.current.openPopup()
      }
      window.addEventListener(EVENT_DRAW_ROUTE, drawRouteHandler)

      return () => {
        window.removeEventListener(EVENT_FLYTO, flyToHandler)
        window.removeEventListener(EVENT_TOGGLE_DISTRICT, toggleDistrictHandler)
        window.removeEventListener(EVENT_SELECT_DISTRICT, selectDistrictHandler)
        window.removeEventListener(EVENT_DRAW_ROUTE, drawRouteHandler)
        // Remove route layer if still on the map
        if (routeLayerRef.current && mapRef.current) {
          mapRef.current.removeLayer(routeLayerRef.current)
          routeLayerRef.current = null
        }
        // Remove demo illustration group + legend if still present
        if (demoIllustrationRef.current && mapRef.current) {
          mapRef.current.removeLayer(demoIllustrationRef.current)
          demoIllustrationRef.current = null
        }
        if (demoLegendRef.current) {
          demoLegendRef.current.remove()
          demoLegendRef.current = null
        }
      }
    }).catch(console.error)

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        layersRef.current = {}
        districtLayersRef.current = new Map()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // React to mode changes
  useEffect(() => {
    if (!mapRef.current) return

    import('leaflet').then((L) => {
      const map = mapRef.current
      if (!map) return

      if (mode === 'sk') {
        // Remove PSK layers if present
        if (layersRef.current.psk) {
          layersRef.current.psk.forEach((l: unknown) => map.removeLayer(l))
          layersRef.current.psk = null
          districtLayersRef.current = new Map()
        }
        // Clear any demo § 44 illustration + legend when leaving PSK detail.
        if (demoIllustrationRef.current) {
          map.removeLayer(demoIllustrationRef.current)
          demoIllustrationRef.current = null
        }
        if (demoLegendRef.current) {
          demoLegendRef.current.remove()
          demoLegendRef.current = null
        }

        // Show SK overview layer — load once
        if (!layersRef.current.sk) {
          fetch('/sk-kraje.geojson')
            .then((r) => r.json())
            .then((geojson) => {
              const skGroup = L.featureGroup()

              // (C) PSK municipalities as grey context polygons — SK overview only
              const muniGroup = L.featureGroup()
              municipalities.forEach((muni) => {
                if (!muni.geom_geojson) return
                const geoJsonLayer = L.geoJSON(muni.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
                  style: {
                    fillColor: '#9ca3af',
                    fillOpacity: 0.05,
                    color: '#6b7280',
                    weight: 0.5,
                  },
                })
                geoJsonLayer.bindTooltip(
                  `${muni.name} · ${muni.schools_count} škôl · ${muni.districts_count} VZN obvodov`,
                  { sticky: true }
                )
                geoJsonLayer.addTo(muniGroup)
              })

              muniGroup.addTo(skGroup)

              L.geoJSON(geojson, {
                style: (feature) => {
                  const name: string = feature?.properties?.name ?? ''
                  const active = isPskKraj(name)
                  return active
                    ? { color: '#7c3aed', weight: 2, fillColor: '#7c3aed', fillOpacity: 0.13 }
                    : { color: '#9ca3af', weight: 1.5, fillColor: '#9ca3af', fillOpacity: 0.07 }
                },
                onEachFeature: (feature, layer) => {
                  const name: string = feature.properties?.name ?? 'Kraj'
                  const active = isPskKraj(name)
                  layer.bindTooltip(
                    `<strong>${name}</strong><br/>${active ? '🟣 Aktívne demo' : '⬜ Pripravujeme'}`,
                    { sticky: true }
                  )
                  layer.on('click', () => {
                    if (active) {
                      setMode('psk')
                    } else {
                      alert(`${name}: Tento kraj zatiaľ nie je pokrytý demo dátami`)
                    }
                  })
                },
              }).addTo(skGroup)

              // Layer control for SK overview
              L.control.layers(
                undefined,
                { 'Obce PSK (665)': muniGroup },
                { collapsed: layerControlCollapsed() }
              ).addTo(map)

              skGroup.addTo(map)
              layersRef.current.sk = skGroup

              map.setView(SK_CENTER, SK_DEFAULT_ZOOM)
            })
            .catch(console.error)
        } else {
          // Layer already built — just re-add and reset view
          layersRef.current.sk.addTo(map)
          map.setView(SK_CENTER, SK_DEFAULT_ZOOM)
        }
      } else {
        // PSK detail mode — hide SK layer
        if (layersRef.current.sk) {
          map.removeLayer(layersRef.current.sk)
        }

        // Build PSK layers if not yet built
        if (!layersRef.current.psk) {
          // (A) Districts: borders-only by default, per-district hue
          const districtsGroup = L.featureGroup()
          const newDistrictLayersMap = new Map()

          if (features.length > 0) {
            // Readability: each obvod must read as its OWN solid coloured
            // region so you can see where it begins and ends. With a 12-entry
            // qualitative palette (distinct hues for adjacent districts) plus a
            // crisp white-cased border, a solid ~0.40 fill makes every district
            // legible while the OSM basemap labels stay faintly visible. The
            // hovered/selected obvod gets a stronger fill and is brought to
            // front so it pops above its neighbours.
            const FILL_OPACITY_DEFAULT = 0.40
            const FILL_OPACITY_HOVER = 0.55
            const WEIGHT_DEFAULT = 2.5
            const WEIGHT_HOVER = 4.5

            // Reset a previously click-selected district back to the default
            // outline-dominant style (faint fill, thin border).
            const resetSelectedDistrict = () => {
              const prevId = selectedDistrictIdRef.current
              if (!prevId) return
              const prevLayer = newDistrictLayersMap.get(prevId)
              if (prevLayer) {
                prevLayer.setStyle({ weight: WEIGHT_DEFAULT, fillOpacity: FILL_OPACITY_DEFAULT })
              }
              selectedDistrictIdRef.current = null
            }

            // Apply the selected/hover style to one district, bring it to front,
            // and remember it as the current selection (resetting the prior one).
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const selectDistrict = (id: string, layer: any) => {
              if (selectedDistrictIdRef.current && selectedDistrictIdRef.current !== id) {
                resetSelectedDistrict()
              }
              layer.setStyle({ weight: WEIGHT_HOVER, fillOpacity: FILL_OPACITY_HOVER })
              layer.bringToFront()
              selectedDistrictIdRef.current = id
            }

            // --- DEMO illustrations (island / overlap / long-distance) -------
            // Remove the demo illustration group + legend if present. Called on
            // every selection change so only the currently-selected RED demo
            // district shows its findings; all other districts stay clean.
            const clearDemoIllustration = () => {
              if (demoIllustrationRef.current) {
                map.removeLayer(demoIllustrationRef.current)
                demoIllustrationRef.current = null
              }
              if (demoLegendRef.current) {
                demoLegendRef.current.remove()
                demoLegendRef.current = null
              }
            }

            // Build + show the geometric illustration for a RED demo district.
            // All geometry is derived from data already on the client:
            //   • island  → islands prop (is_demo, district_id === Šmeralova)
            //   • overlap → overlaps prop (is_demo, district in {a,b})
            //   • long-distance → school point + farthest district vertex
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const drawDemoIllustration = (feature: any) => {
              clearDemoIllustration()
              if (!DEMO_RED_DISTRICT_IDS.has(feature.id)) return

              const group = L.featureGroup()
              const legendRows: string[] = []

              // (1) ISLAND / strip — detached fragment that belongs elsewhere.
              islands
                .filter(
                  (isl) =>
                    isl.is_demo === true &&
                    isl.district_id === feature.id &&
                    isl.geom_geojson
                )
                .forEach((isl) => {
                  L.geoJSON(isl.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
                    style: {
                      color: '#b91c1c', // red-700 outline
                      weight: 3,
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      fillColor: 'url(#mrkHatch)' as any, // hatched → reads as anomaly
                      fillOpacity: 1,
                      dashArray: '6,4',
                    },
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    pane: 'overlaps' as any,
                  })
                    .bindTooltip(
                      '<strong>ostrov (S2)</strong><br/>Odčlenená lišta v obvode patrí inému obvodu.',
                      { sticky: true }
                    )
                    .addTo(group)
                })
              if (
                islands.some(
                  (isl) => isl.is_demo === true && isl.district_id === feature.id && isl.geom_geojson
                )
              ) {
                legendRows.push(
                  '<span style="display:inline-block;width:12px;height:12px;border:2px dashed #b91c1c;background:repeating-linear-gradient(45deg,#7c3aed,#7c3aed 2px,transparent 2px,transparent 5px);margin-right:6px;vertical-align:-2px"></span>ostrov (S2)'
                )
              }

              // (2) OVERLAP — same street segment claimed by two districts.
              const myOverlaps = overlaps.filter(
                (ov) =>
                  ov.is_demo === true &&
                  ov.overlap_geojson &&
                  (ov.district_a_id === feature.id || ov.district_b_id === feature.id)
              )
              myOverlaps.forEach((ov) => {
                const other =
                  ov.district_a_id === feature.id ? ov.district_b_name : ov.district_a_name
                L.geoJSON(ov.overlap_geojson as unknown as GeoJSON.GeoJsonObject, {
                  style: {
                    fillColor: '#facc15', // amber-400 high-visibility
                    fillOpacity: 0.6,
                    color: '#b45309', // amber-700 border
                    weight: 3,
                    dashArray: '6,4',
                  },
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  pane: 'overlaps' as any,
                })
                  .bindTooltip(
                    `<strong>prekryv ulice (S2)</strong><br/>Zdieľané s obvodom ${other}.`,
                    { sticky: true }
                  )
                  .addTo(group)
              })
              if (myOverlaps.length > 0) {
                legendRows.push(
                  '<span style="display:inline-block;width:12px;height:12px;border:2px dashed #b45309;background:#facc15;margin-right:6px;vertical-align:-2px"></span>prekryv ulice (S2)'
                )
              }

              // (3) LONG DISTANCE (Pa) — dashed line school → farthest in-district
              // vertex. Drawn ONLY for Šmeralova, the one demo district whose
              // seed carries a Pa = RISK finding (Mirka Nešpora's Pa is PASS, so
              // it must NOT get a distance line). The line geometry itself is
              // derived from the polygon's farthest vertex; we still require the
              // air-line to exceed the 2 km first-grade threshold.
              const schoolGeom = feature.school_geom_geojson as
                | { type: string; coordinates: [number, number] }
                | null
              if (feature.id === DEMO_DISTRICT_SMERALOVA && schoolGeom && schoolGeom.type === 'Point') {
                const [slon, slat] = schoolGeom.coordinates
                const school: [number, number] = [slat, slon]
                const far = farthestVertexFromSchool(feature.geom_geojson, school)
                if (far && far.meters > 2000) {
                  const km = (far.meters / 1000).toFixed(1)
                  L.polyline([school, far.point], {
                    color: '#dc2626', // red-600
                    weight: 3,
                    dashArray: '8,5',
                    opacity: 0.9,
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    pane: 'overlaps' as any,
                  })
                    .bindTooltip(
                      `<strong>~${km} km (Pa)</strong><br/>Najvzdialenejšia adresa 1. stupňa od školy (vzdušná čiara).`,
                      { sticky: true }
                    )
                    .addTo(group)
                  // Small marker at the far end to anchor the label.
                  L.marker(far.point, {
                    icon: L.divIcon({
                      html: `<div style="background:#dc2626;color:#fff;font-size:11px;font-weight:700;padding:1px 5px;border-radius:4px;white-space:nowrap;box-shadow:0 1px 2px rgba(0,0,0,.4)">~${km} km (Pa)</div>`,
                      className: 'demo-distance-label',
                      iconSize: [0, 0],
                      iconAnchor: [0, 0],
                    }),
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    pane: 'overlaps' as any,
                  }).addTo(group)
                  legendRows.push(
                    `<span style="display:inline-block;width:14px;height:0;border-top:3px dashed #dc2626;margin-right:6px;vertical-align:3px"></span>~${km} km (Pa)`
                  )
                }
              }

              if (legendRows.length === 0) return

              group.addTo(map)
              demoIllustrationRef.current = group

              // Legend box (bottom-left, above attribution) summarising the
              // demo findings drawn for this district. Pure DOM so it does not
              // disturb the Leaflet layer control on the right.
              const legend = document.createElement('div')
              legend.className = 'demo-finding-legend'
              legend.style.cssText =
                'position:absolute;left:8px;bottom:24px;z-index:1000;background:rgba(255,255,255,.95);border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;font-size:11px;line-height:1.7;box-shadow:0 1px 4px rgba(0,0,0,.2);max-width:230px;pointer-events:none'
              legend.innerHTML =
                `<div style="font-weight:700;margin-bottom:4px">Nálezy § 44 (demo)</div>${legendRows.join('<br/>')}`
              containerRef.current?.appendChild(legend)
              demoLegendRef.current = legend
            }

            // Expose to the init-effect's EVENT_SELECT_DISTRICT handler so that
            // selecting a district from the findings panel also surfaces its
            // demo § 44 illustration (same behaviour as tapping the polygon).
            drawDemoRef.current = drawDemoIllustration

            // Tapping the empty map (outside any polygon) clears the highlight
            // and any demo illustration.
            map.on('click', () => {
              resetSelectedDistrict()
              clearDemoIllustration()
            })

            features.forEach((feature, index) => {
              if (!feature.geom_geojson) return

              const hue = getDistrictHue(index)
              const borderColor = `hsl(${hue}, 70%, 38%)`
              const fillColor = `hsl(${hue}, 65%, 55%)`

              // White casing line drawn UNDER the coloured border so adjacent
              // obvod borders read as two distinct edges instead of one blur.
              const casingLayer = L.geoJSON(feature.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
                style: {
                  color: '#ffffff',
                  weight: WEIGHT_DEFAULT + 2.5,
                  opacity: 0.9,
                  fillOpacity: 0,
                  interactive: false,
                },
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                pane: 'districts' as any,
              })
              casingLayer.addTo(districtsGroup)

              const geoJsonLayer = L.geoJSON(feature.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
                style: {
                  color: borderColor,
                  weight: WEIGHT_DEFAULT,
                  fillColor,
                  fillOpacity: FILL_OPACITY_DEFAULT,
                },
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                pane: 'districts' as any,
              })

              const colorConfig = COMPOSITION_COLOR_MAP[feature.composition_color] ?? COMPOSITION_COLOR_MAP.NONE
              const symbol = colorConfig.symbol

              geoJsonLayer.bindTooltip(
                `<strong>${feature.name}</strong><br/>${symbol} ${feature.composition_color ?? 'NONE'}${feature.composition_reason ? `<br/><em>${feature.composition_reason}</em>` : ''}`,
                { sticky: true }
              )

              geoJsonLayer.on('mouseover', () => {
                geoJsonLayer.setStyle({ weight: WEIGHT_HOVER, fillOpacity: FILL_OPACITY_HOVER })
                geoJsonLayer.bringToFront()
              })
              geoJsonLayer.on('mouseout', () => {
                // Keep the click-selected district highlighted on mouseout.
                if (selectedDistrictIdRef.current === feature.id) return
                geoJsonLayer.setStyle({ weight: WEIGHT_DEFAULT, fillOpacity: FILL_OPACITY_DEFAULT })
              })

              // Bind the district SUMMARY popup (same builder family as the
              // school popup). maxWidth/autoPan keep it mobile-friendly.
              geoJsonLayer.bindPopup(
                buildDistrictSummaryPopup(
                  feature.name,
                  feature.id,
                  districtSummaries[feature.id],
                  feature.composition_color
                ),
                { maxWidth: 280, autoPan: true, autoPanPadding: [20, 20] }
              )

              // Tap the polygon body → highlight it (bring to front + stronger
              // fill, reset any prior selection) and open the summary popup at
              // the tap point. No auto-navigation — the popup's detail link is
              // the way to open /districts/[id].
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              geoJsonLayer.on('click', (e: any) => {
                // Don't let the click bubble to the map background handler,
                // which would immediately clear the highlight we just set.
                L.DomEvent.stopPropagation(e)
                selectDistrict(feature.id, geoJsonLayer)
                // Surface the geometric § 44 illustration for the two RED demo
                // districts; a no-op (just clears) for every other obvod.
                drawDemoIllustration(feature)
                geoJsonLayer.openPopup(e.latlng)
              })

              // Closing the popup clears the highlight (unless another district
              // was selected in the meantime) and removes the demo illustration.
              geoJsonLayer.on('popupclose', () => {
                if (selectedDistrictIdRef.current === feature.id) {
                  geoJsonLayer.setStyle({ weight: WEIGHT_DEFAULT, fillOpacity: FILL_OPACITY_DEFAULT })
                  selectedDistrictIdRef.current = null
                  clearDemoIllustration()
                }
              })

              geoJsonLayer.addTo(districtsGroup)
              newDistrictLayersMap.set(feature.id, geoJsonLayer)
            })

            districtLayersRef.current = newDistrictLayersMap

            try {
              const bounds = districtsGroup.getBounds()
              if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [20, 20] })
              }
            } catch {
              map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
            }
          } else {
            map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
          }

          districtsGroup.addTo(map)

          // (B) School markers as divIcon SVG
          const districtLinkedSchoolNames = new Set(
            features.filter((f) => f.school_name).map((f) => f.school_name!)
          )

          const schoolsGroup = L.featureGroup()

          // Pin colour distinguishes founder: public (zriaďovateľ mesto Prešov)
          // = blue; private/church = amber. White "Š" + stroke kept for
          // legibility on both.
          const SCHOOL_COLOR_PUBLIC = '#2563eb'
          const SCHOOL_COLOR_PRIVATE = '#d97706'
          const makeSchoolIcon = (size: number, fill: string = SCHOOL_COLOR_PUBLIC) => L.divIcon({
            html: `<div style="line-height:0"><svg viewBox="0 0 24 24" width="${size}" height="${size}"><circle cx="12" cy="12" r="10" fill="${fill}" stroke="#fff" stroke-width="2"/><text x="12" y="16" text-anchor="middle" fill="#fff" font-size="12" font-weight="700">Š</text></svg></div>`,
            className: 'school-icon',
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
          })

          features.forEach((feature) => {
            if (!feature.school_geom_geojson) return
            const geom = feature.school_geom_geojson as { type: string; coordinates: [number, number] }
            if (geom.type !== 'Point') return
            const [lon, lat] = geom.coordinates
            const schoolName = feature.school_name ?? 'Škola'
            L.marker([lat, lon], {
              icon: makeSchoolIcon(22),
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'schools' as any,
            })
              // Short hover hint; the click popup carries the semafor + numbers.
              .bindTooltip(schoolName)
              .bindPopup(
                buildDistrictSchoolPopup(
                  schoolName,
                  feature.id,
                  districtSummaries[feature.id],
                  feature.composition_color
                ),
                { maxWidth: 280, autoPanPadding: [20, 20] }
              )
              .addTo(schoolsGroup)
          })

          schools.forEach((school) => {
            if (!school.geom_geojson) return
            if (districtLinkedSchoolNames.has(school.name)) return
            const geom = school.geom_geojson as { type: string; coordinates: [number, number] }
            if (geom.type !== 'Point') return
            const [lon, lat] = geom.coordinates
            const isPrivate = school.is_public === false
            const fill = isPrivate ? SCHOOL_COLOR_PRIVATE : SCHOOL_COLOR_PUBLIC
            L.marker([lat, lon], {
              icon: makeSchoolIcon(16, fill),
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'schools' as any,
            })
              .bindTooltip(school.name)
              .bindPopup(
                buildNonVznSchoolPopup(school.name, school.kind, isPrivate),
                { maxWidth: 280, autoPanPadding: [20, 20] }
              )
              .addTo(schoolsGroup)
          })

          schoolsGroup.addTo(map)

          // MRK overlays with hatch pattern
          const mrkGroup = L.featureGroup()

          mrkOverlays.forEach((mrk) => {
            if (!mrk.geom_geojson) return
            const geoJsonLayer = L.geoJSON(mrk.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: {
                color: '#5b21b6',
                weight: 1.5,
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                fillColor: 'url(#mrkHatch)' as any,
                fillOpacity: 1,
                // Non-interactive so a tap on a district area that overlaps an
                // MRK locality always reaches the district polygon underneath
                // and opens the district summary popup (never an MRK popup).
                interactive: false,
              },
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'mrk' as any,
            })
            geoJsonLayer.addTo(mrkGroup)
          })

          // MRK stays OFF by default (declutter): the group is built and
          // registered in the layer control below ("MRK lokality …") but is
          // NOT added to the map on load. The user can enable it via the
          // checkbox. Do not call mrkGroup.addTo(map) here.

          // (B-heatmap) Overlap polygons — Sprint M-3 styling. Demo overlaps
          // get a saturated yellow fill + dashed amber border so the viewer
          // can pick them out from real geom-derived overlaps (red, no border,
          // multiply blend). The pane-level mixBlendMode = 'multiply' (set up
          // above) means stacked polygons still darken visually.
          const overlapsGroup = L.featureGroup()

          overlaps.forEach((overlap) => {
            if (!overlap.overlap_geojson) return
            const isDemo = overlap.is_demo === true
            const style = isDemo
              ? {
                  fillColor: '#facc15', // amber-400 — high-visibility hatched yellow
                  fillOpacity: 0.55,
                  color: '#b45309',     // amber-700 border
                  weight: 2,
                  dashArray: '6,4',
                }
              : {
                  fillColor: '#dc2626',
                  fillOpacity: 0.10,
                  color: 'transparent',
                  weight: 0,
                }
            const geoJsonLayer = L.geoJSON(overlap.overlap_geojson as unknown as GeoJSON.GeoJsonObject, {
              style,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'overlaps' as any,
            })
            const areaHa = (overlap.overlap_area_m2 / 10000).toFixed(2)
            const tooltip = isDemo
              ? `<strong>⚠ PREKRYV (demo)</strong>: tieto adresy patria podľa VZN do 2 obvodov<br/>` +
                `${overlap.district_a_name} × ${overlap.district_b_name}<br/>` +
                `Plocha: ${areaHa} ha · <em>§ 44 zákona 321 §3 violation</em>`
              : `Prekryv obvodov: ${overlap.district_a_name} × ${overlap.district_b_name}<br/>` +
                `Plocha: ${areaHa} ha`
            geoJsonLayer.bindTooltip(tooltip, { sticky: true })
            geoJsonLayer.addTo(overlapsGroup)
          })

          // (M-3) District island anomalies — rendered as red dashed outlines
          // with no fill, so the underlying clean/voronoi obvod still reads.
          // Only islands flagged with anomaly_type (demo segregation seed +
          // any future engine-flagged real islands) are drawn — the default
          // 'main_body' / 'reconnected' statuses stay off the map to avoid
          // visual noise.
          const islandsGroup = L.featureGroup()
          islands
            .filter((isl) =>
              isl.anomaly_type != null ||
              isl.status === 'unresolved_anomaly' ||
              isl.is_demo === true
            )
            .forEach((isl) => {
              if (!isl.geom_geojson) return
              const isDemo = isl.is_demo === true
              const layer = L.geoJSON(isl.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
                style: {
                  color: '#b91c1c', // red-700
                  weight: 3,
                  fillColor: '#b91c1c',
                  fillOpacity: 0,
                  dashArray: '6,4',
                },
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                pane: 'overlaps' as any,
              })
              const areaHa =
                isl.area_m2 != null ? `${(Number(isl.area_m2) / 10000).toFixed(2)} ha` : '?'
              const tooltip = isDemo
                ? `<strong>⚠ OSTROV (demo)</strong>: časť obvodu odtrhnutá od hlavnej plochy.<br/>` +
                  `Možná segregácia (§ 44 zákona 321 §3 violation).<br/>` +
                  `Plocha: ${areaHa}`
                : `<strong>Ostrov obvodu</strong><br/>` +
                  `${isl.anomaly_type ?? isl.status ?? 'anomália'}<br/>` +
                  `Plocha: ${areaHa}`
              layer.bindTooltip(tooltip, { sticky: true })
              layer.addTo(islandsGroup)
            })

          // (G) Street geocode points layer
          const streetPointsGroup = L.featureGroup()
          streetGeocodes.forEach((sg) => {
            if (sg.lat == null || sg.lon == null) return
            const marker = L.circleMarker([sg.lat, sg.lon], {
              radius: 3,
              fillColor: '#10b981',
              color: '#047857',
              weight: 1,
              fillOpacity: 0.7,
            })
            marker.bindTooltip(
              `${sg.street}${sg.partial_match ? ' ⚠ partial' : ''}`,
              { sticky: true }
            )
            marker.addTo(streetPointsGroup)
          })

          // (H) House points layer — per-house geocodes from VZN ranges
          // Build district_id → index map for HSL hue lookup
          const districtIndexMap = new Map<string, number>()
          features.forEach((f, idx) => { districtIndexMap.set(f.id, idx) })

          const housePointsGroup = L.featureGroup()
          housePoints.forEach((hp) => {
            if (hp.lat == null || hp.lon == null) return
            // Only render valid points by default; invalid are silently skipped
            if (hp.valid === false) return

            const distIdx = districtIndexMap.get(hp.district_id) ?? 0
            const hue = getDistrictHue(distIdx)
            const fillColor = `hsl(${hue}, 70%, 45%)`
            const strokeColor = `hsl(${hue}, 70%, 25%)`

            const marker = L.circleMarker([hp.lat, hp.lon], {
              radius: 2.5,
              fillColor,
              color: strokeColor,
              weight: 0.7,
              fillOpacity: 0.85,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'streetPoints' as any,
            })
            const partialWarning = hp.partial_match ? ' ⚠ partial match' : ''
            marker.bindTooltip(
              `${hp.street} ${hp.house_number}${hp.formatted_address ? `<br/>${hp.formatted_address}` : ''}${partialWarning}`,
              { sticky: true }
            )
            marker.addTo(housePointsGroup)
          })

          // (K) Voronoi boundary layer — Sprint K
          const voronoiGroup = L.featureGroup()

          // Build district index map for hue lookup (reuse districtIndexMap)
          voronoiGeom.forEach((v) => {
            if (!v.geom_voronoi_geojson) return
            const distIdx = districtIndexMap.get(v.id) ?? (features.findIndex((f) => f.id === v.id))
            const hue = getDistrictHue(distIdx >= 0 ? distIdx : 0)
            const fillColor = `hsl(${hue}, 65%, 60%)`
            const borderColor = `hsl(${hue}, 65%, 35%)`

            const layer = L.geoJSON(v.geom_voronoi_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: {
                color: borderColor,
                weight: 2,
                fillColor,
                fillOpacity: 0.25,
              },
            })
            const meta = v.geom_voronoi_metadata
            const cells = meta?.cell_count ?? '?'
            layer.bindTooltip(
              `<strong>${v.name}</strong><br/>Voronoi (Sprint K)<br/>${cells} buniek · 0 prekryvov`,
              { sticky: true }
            )
            layer.addTo(voronoiGroup)
          })

          // (M-2) Clean district boundary layer — primary "Obvody" surface
          // when present. Hand-tuned showcase polygons get a thicker border;
          // voronoi_fallback polygons get the same weight as Sprint A so the
          // map still reads as a single coherent layer.
          const cleanGroup = L.featureGroup()
          cleanGeom.forEach((cg) => {
            if (!cg.geom_clean_geojson) return
            const distIdx = districtIndexMap.get(cg.id) ?? features.findIndex((f) => f.id === cg.id)
            const hue = getDistrictHue(distIdx >= 0 ? distIdx : 0)
            const fillColor = `hsl(${hue}, 65%, 60%)`
            const borderColor = `hsl(${hue}, 65%, 40%)`
            const method = cg.geom_clean_metadata?.method ?? 'voronoi_fallback'
            const isShowcase = method === 'clean_polygon'

            const layer = L.geoJSON(cg.geom_clean_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: {
                color: borderColor,
                weight: isShowcase ? 3.5 : 3,
                fillColor,
                fillOpacity: 0.25,
                dashArray: isShowcase ? undefined : '4,3',
              },
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'districts' as any,
            })
            const label = isShowcase
              ? 'Demo clean polygón (hand-tuned)'
              : 'Voronoi fallback'
            layer.bindTooltip(
              `<strong>${cg.name}</strong><br/>${label}`,
              { sticky: true }
            )
            layer.on('click', () => {
              router.push(`/districts/${cg.id}`)
            })
            layer.addTo(cleanGroup)
          })

          // (M-2) Per-house dots — only visible when zoomed in past
          // HOUSE_DOTS_MIN_ZOOM. We build the markers eagerly but gate the
          // group's addTo/removeFrom on the map's zoom level.
          const houseDotsGroup = L.featureGroup()
          houseDots.forEach((hd) => {
            if (hd.lat == null || hd.lon == null) return
            const distIdx = districtIndexMap.get(hd.district_id) ?? 0
            const hue = getDistrictHue(distIdx)
            const marker = L.circleMarker([hd.lat, hd.lon], {
              radius: 3,
              fillColor: `hsl(${hue}, 70%, 45%)`,
              color: `hsl(${hue}, 70%, 25%)`,
              weight: 0.8,
              fillOpacity: 0.9,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'streetPoints' as any,
            })
            marker.bindTooltip(`${hd.street} ${hd.house_number}`, { sticky: true })
            marker.addTo(houseDotsGroup)
          })

          // House dots are OFF by default. They only render once the user
          // explicitly toggles the "Adresné bodky" layer on AND has zoomed in
          // past HOUSE_DOTS_MIN_ZOOM. We track the toggle intent via the layer
          // control's overlayadd/overlayremove events so the zoom listener
          // never re-introduces the dots on its own.
          let houseDotsEnabled = false
          const updateHouseDotsVisibility = () => {
            const z = map.getZoom()
            if (houseDotsEnabled && z >= HOUSE_DOTS_MIN_ZOOM) {
              if (!map.hasLayer(houseDotsGroup)) map.addLayer(houseDotsGroup)
            } else {
              if (map.hasLayer(houseDotsGroup)) map.removeLayer(houseDotsGroup)
            }
          }
          map.on('zoomend', updateHouseDotsVisibility)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          map.on('overlayadd', (e: any) => {
            if (e.layer === houseDotsGroup) {
              houseDotsEnabled = true
              updateHouseDotsVisibility()
            }
          })
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          map.on('overlayremove', (e: any) => {
            if (e.layer === houseDotsGroup) {
              houseDotsEnabled = false
              updateHouseDotsVisibility()
            }
          })

          // Layer control — MVP demo view. The authoritative "Obvody" layer is
          // the corrected geometry served via so_district_map_features (the
          // `features` prop → districtsGroup). The older Sprint M-2 clean-geom
          // surface (cleanGroup) is now STALE relative to the corrected
          // districts.geom — for several central districts it holds collapsed
          // voronoi_fallback polygons that are 17×–6000× smaller than the real
          // extent — so it is exposed only as an optional comparison toggle and
          // is NOT drawn by default. Voronoi remains engine input only and is
          // hidden from the user-facing control.
          const overlays: Record<string, unknown> = {}
          overlays[`Obvody (${features.length})`] = districtsGroup
          // NOTE: "Obvody — staršie clean polygóny" (Sprint M-2 cleanGroup) removed from
          // layer control (bod 8b). The authoritative district polygons come from
          // so_district_map_features (districtsGroup above). cleanGroup is legacy/duplicate.
          overlays[`Školy (${schools.length})`] = schoolsGroup
          overlays['Prekryvy obvodov (kde 2+ obvodov hovorí o tej istej adrese)'] = overlapsGroup
          const anomalyIslandsCount = islands.filter(
            (i) => i.anomaly_type != null || i.status === 'unresolved_anomaly' || i.is_demo === true
          ).length
          if (anomalyIslandsCount > 0) {
            overlays[`Anomálie / ostrovy (${anomalyIslandsCount})`] = islandsGroup
          }
          overlays['MRK lokality (Atlas marginalizovaných rómskych komunít)'] = mrkGroup
          // Expert layers (off by default — analyst evidence, not for normal view)
          overlays['⚙ Expert: Domy z VZN (Google geokódovanie, 460 platných)'] = housePointsGroup
          if (houseDots.length > 0) {
            overlays[`Adresné bodky obvodov (auto-zobrazia sa pri priblížení ≥ ${HOUSE_DOTS_MIN_ZOOM})`] = houseDotsGroup
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const layersControl = L.control.layers(undefined, overlays as any, {
            collapsed: layerControlCollapsed(),
          }).addTo(map)
          // Label the collapsed toggle so mobile users recognise it as "Vrstvy".
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const layersToggle = (layersControl as any)._container?.querySelector(
            '.leaflet-control-layers-toggle'
          ) as HTMLElement | null
          if (layersToggle) {
            layersToggle.setAttribute('title', 'Vrstvy mapy')
            layersToggle.setAttribute('aria-label', 'Vrstvy mapy')
          }

          // Default ON: ONLY the corrected obvody (distinct solid fills) +
          // school pins, for a clean, readable high-level map. Every analytical
          // overlay (MRK, anomálie/ostrovy, prekryvy, domy/house-dots, stale
          // cleanGroup) stays OFF by default and is reachable via the layer
          // control for drill-down.
          districtsGroup.addTo(map)
          schoolsGroup.addTo(map)

          // Fit bounds to the authoritative districtsGroup (corrected geom).
          try {
            const bounds = districtsGroup.getBounds()
            if (bounds.isValid()) {
              map.fitBounds(bounds, { padding: [20, 20] })
            }
          } catch {
            map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
          }

          layersRef.current.psk = [districtsGroup, schoolsGroup, mrkGroup, overlapsGroup, streetPointsGroup, housePointsGroup, voronoiGroup, cleanGroup, houseDotsGroup, islandsGroup]
        } else {
          const [districtsGroup, schoolsGroup] = layersRef.current.psk
          // Re-add ONLY the default-ON layers (corrected obvody + školy); every
          // analytical overlay stays OFF by default and is toggled via the
          // layer control.
          districtsGroup.addTo(map)
          schoolsGroup.addTo(map)
          if (features.length > 0) {
            try {
              const bounds = districtsGroup.getBounds()
              if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [20, 20] })
              }
            } catch {
              map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
            }
          } else {
            map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
          }
        }
      }
    }).catch(console.error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, mapReady])

  return (
    <div className="relative w-full h-full">
      {mode === 'psk' && (
        <button
          onClick={() => setMode('sk')}
          className="absolute top-2 left-2 z-[1000] rounded bg-white border border-border px-3 py-1.5 text-xs font-medium shadow hover:bg-accent transition-colors"
          aria-label="Späť na prehľad Slovenska"
        >
          ← Späť na Slovensko
        </button>
      )}
      <div
        ref={containerRef}
        className="w-full h-full"
        role="application"
        aria-label="Interaktívna mapa školských obvodov Prešova"
        aria-describedby="map-fallback-table"
        tabIndex={0}
      />
    </div>
  )
}
