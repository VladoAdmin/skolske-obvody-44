'use client'

import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoMrkLocality, SoPskMunicipality, SoHousePoint, SoHouseDot, SoDistrictStreetLine, SoFindingsPanelItem, SoStreetCoverageGap, SoBarrier } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, SK_CENTER, SK_DEFAULT_ZOOM, PSK_KRAJ_NAMES, getDistrictHue } from '@/lib/config/region'
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
import { getSeverityClass, getSeverityLabel } from '@/lib/format/severity'
import { EVIDENCE_TRAIL_LABELS_SK } from '@/lib/compliance/labels'

// Zoom threshold (inclusive) at which per-house dots become visible.
const HOUSE_DOTS_MIN_ZOOM = 16


// The Leaflet layer-toggle control starts COLLAPSED at every width (item 16) so
// it never obscures the map; it expands into the full checkbox list on
// hover/click. Styled as a labelled "Vrstvy" pill in app/globals.css.
function layerControlCollapsed(): boolean {
  return true
}

interface RegionMapClientProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  mrkLocalities?: SoMrkLocality[]
  municipalities?: SoPskMunicipality[]  // PSK kraj context in the SK overview
  // Streets pivot: each district drawn as its VZN-assigned street lines.
  streetLines?: SoDistrictStreetLine[]
  housePoints?: SoHousePoint[]
  houseDots?: SoHouseDot[]
  // VLA-14: engine-classified uncovered streets (vzn_gap). The client only
  // draws + labels what the engine wrote — never classifies.
  coverageGaps?: SoStreetCoverageGap[]
  // VLA-20: barrier input rows — the seeded railway is FICTIONAL (is_demo),
  // so the layer must always badge demo rows as DEMO.
  barriers?: SoBarrier[]
  // Engine findings (§ 44 demo scenarios included) — drives the per-district
  // evidence legend shown on selection. Never used to derive colour/severity
  // client-side; severity/text come straight from the engine output row.
  findings?: SoFindingsPanelItem[]
  districtSummaries?: Record<string, DistrictPopupSummary>
  initialMode?: 'sk' | 'psk'
}

function isPskKraj(name: string): boolean {
  const lower = name.toLowerCase()
  return PSK_KRAJ_NAMES.some((n) => lower.includes(n.toLowerCase()))
}

export function RegionMapClient({ features, schools, mrkLocalities = [], municipalities = [], streetLines = [], housePoints = [], coverageGaps = [], barriers = [], findings = [], districtSummaries = {}, initialMode = 'sk' }: RegionMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
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
  // Home / reset-view bridge (item 13): restores default center/zoom + default
  // layer visibility. Populated by the PSK mode effect, called by the overlay
  // Home button.
  const homeResetRef = useRef<(() => void) | null>(null)
  // Bridge to clear the demo illustration + selection from outside the mode
  // effect (used by the Esc-to-dismiss keyboard handler).
  const clearDemoRef = useRef<(() => void) | null>(null)
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

      // --- CustomEvent: select district (highlight its STREETS + flyTo) ---
      // Streets pivot: each district's "layer" is a featureGroup of its coloured
      // street lines. Selecting highlights that district's streets (full
      // weight/opacity) and dims every other district's streets.
      const selectDistrictHandler = (e: Event) => {
        const { id } = (e as CustomEvent<SelectDistrictDetail>).detail
        districtLayersRef.current.forEach((layer, layerId) => {
          const featureIndex = features.findIndex((f) => f.id === layerId)
          const hue = getDistrictHue(featureIndex >= 0 ? featureIndex : 0)
          if (layerId === id) {
            layer.setStyle({ weight: 5, opacity: 1 })
            layer.bringToFront()
            selectedDistrictIdRef.current = id
            try {
              const bounds = layer.getBounds()
              if (bounds.isValid()) {
                map.flyToBounds(bounds, { padding: [30, 30], duration: 1 })
              }
            } catch { /* ignore */ }
            // Open the district summary popup so the detail is surfaced on the map.
            try { layer.openPopup() } catch { /* ignore */ }
          } else {
            // dim every other district's streets
            layer.setStyle({ weight: 2, opacity: 0.25, color: `hsl(${hue}, 45%, 55%)` })
          }
        })
        // VLA-15: route the panel→map selection through the streets-pivot
        // selectDistrict bridge too, so the district evidence legend (short
        // trail + register link) renders — same as a direct street tap.
        if (drawDemoRef.current) drawDemoRef.current({ id })
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

      // Esc dismisses the open district popup + clears the selection and the
      // § 44 illustration (in addition to outside-map click and other-district).
      const escHandler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          if (clearDemoRef.current) clearDemoRef.current()
          else { try { map.closePopup() } catch { /* ignore */ } }
        }
      }
      window.addEventListener('keydown', escHandler)

      return () => {
        window.removeEventListener(EVENT_FLYTO, flyToHandler)
        window.removeEventListener(EVENT_TOGGLE_DISTRICT, toggleDistrictHandler)
        window.removeEventListener(EVENT_SELECT_DISTRICT, selectDistrictHandler)
        window.removeEventListener(EVENT_DRAW_ROUTE, drawRouteHandler)
        window.removeEventListener('keydown', escHandler)
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
          // (A) Districts as their STREETS (streets pivot). Each district is the
          // set of its VZN-assigned streets, drawn as coloured linestrings in the
          // district's stable hue. A street shared by 2+ districts is drawn in
          // each district's colour (NOT a finding). The ~5% VZN streets with no
          // OSM line fall back to a small dot in the same colour, so no street is
          // missing. districtLayersRef maps district_id → its street featureGroup
          // for the select/highlight/toggle bridges in the init effect.
          const districtsGroup = L.featureGroup()
          const newDistrictLayersMap = new Map()

          // Build district_id → index map for the stable per-district hue.
          const districtIndexMap = new Map<string, number>()
          features.forEach((f, idx) => { districtIndexMap.set(f.id, idx) })

          const STREET_WEIGHT_DEFAULT = 3
          const STREET_WEIGHT_HOVER = 5

          if (features.length > 0) {
            // Group street segments by district.
            const linesByDistrict = new Map<string, SoDistrictStreetLine[]>()
            for (const sl of streetLines) {
              if (!sl.linestring_geojson) continue
              const arr = linesByDistrict.get(sl.district_id) ?? []
              arr.push(sl)
              linesByDistrict.set(sl.district_id, arr)
            }

            // Per-district § 44 evidence legend — built ONLY from engine findings
            // rows (condition_label_sk, severity, evidence_public_text, is_demo).
            // No client-side verdict/colour logic: severity class + label come
            // straight from lib/format/severity, the same helper the findings
            // register uses, so the map never invents a red/orange state.
            const clearEvidenceLegend = () => {
              if (demoLegendRef.current) {
                demoLegendRef.current.remove()
                demoLegendRef.current = null
              }
            }
            const showEvidenceLegend = (id: string) => {
              clearEvidenceLegend()
              const districtFindings = findings.filter((f) => f.district_id === id)
              if (districtFindings.length === 0 || !containerRef.current) return
              const rows = districtFindings
                .map((f) => {
                  const cls = getSeverityClass(f.severity)
                  const label = getSeverityLabel(f.severity)
                  const demoTag = f.is_demo
                    ? '<span style="font-weight:600;color:#b45309">DEMO</span> · '
                    : ''
                  // VLA-15: short evidence trail — the Slovak conclusion of the
                  // street-level verdict + deep link to the register entry
                  // (auto-expands the full "Ako sme na to prišli" section there).
                  const conclusion = f.evidence_trail?.conclusion_sk
                    ? `<div style="color:#374151;font-size:11px;margin-top:2px"><strong>${EVIDENCE_TRAIL_LABELS_SK.conclusion_sk}:</strong> ${f.evidence_trail.conclusion_sk}</div>`
                    : ''
                  const registerLink = `<a href="/findings#f-${f.finding_id}" style="font-size:11px;color:#1d4ed8;text-decoration:underline">${EVIDENCE_TRAIL_LABELS_SK.registerLink}</a>`
                  return `<div style="margin-bottom:5px"><span class="${cls}" style="display:inline-block;border-radius:4px;border-width:1px;border-style:solid;padding:0 5px;font-size:10px;font-weight:600;margin-right:5px">${label}</span>${demoTag}<strong>${f.condition_label_sk}</strong>${f.evidence_public_text ? `<div style="color:#4b5563;font-size:11px;margin-top:1px">${f.evidence_public_text}</div>` : ''}${conclusion}${registerLink}</div>`
                })
                .join('')
              const legend = document.createElement('div')
              legend.className = 'district-evidence-legend'
              legend.style.cssText =
                'position:absolute;left:8px;bottom:24px;z-index:1000;background:rgba(255,255,255,.97);border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;font-size:11px;line-height:1.5;box-shadow:0 1px 4px rgba(0,0,0,.2);max-width:260px;max-height:220px;overflow:auto'
              legend.innerHTML =
                `<div style="font-weight:700;margin-bottom:5px">Nálezy § 44 obvodu</div>${rows}`
              containerRef.current.appendChild(legend)
              demoLegendRef.current = legend
            }

            // Highlight one district's streets (full weight/opacity) and dim all
            // others. Brings the selected group to front.
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const selectDistrict = (id: string) => {
              newDistrictLayersMap.forEach((grp, gid) => {
                const idx = districtIndexMap.get(gid) ?? 0
                const hue = getDistrictHue(idx)
                if (gid === id) {
                  grp.setStyle({ weight: STREET_WEIGHT_HOVER, opacity: 1, color: `hsl(${hue}, 70%, 38%)` })
                  grp.bringToFront()
                } else {
                  grp.setStyle({ weight: 2, opacity: 0.22, color: `hsl(${hue}, 45%, 58%)` })
                }
              })
              selectedDistrictIdRef.current = id
              showEvidenceLegend(id)
            }

            // Clear selection: restore every district's streets to default.
            const clearSelection = () => {
              newDistrictLayersMap.forEach((grp, gid) => {
                const idx = districtIndexMap.get(gid) ?? 0
                const hue = getDistrictHue(idx)
                grp.setStyle({ weight: STREET_WEIGHT_DEFAULT, opacity: 0.9, color: `hsl(${hue}, 65%, 42%)` })
              })
              selectedDistrictIdRef.current = null
              clearEvidenceLegend()
            }

            // Expose clear to the Esc handler / Home reset bridges.
            clearDemoRef.current = () => {
              try { map.closePopup() } catch { /* ignore */ }
              clearSelection()
            }
            // drawDemoRef is unused in the streets pivot (no § 44 illustrations in
            // step 1). Point it at the plain selection so the panel→map bridge
            // still highlights the chosen district's streets.
            drawDemoRef.current = (feature: { id: string }) => selectDistrict(feature.id)

            // Tapping empty map clears any selection.
            map.on('click', () => { clearSelection() })

            // Render stats for the E2E street-coverage gate (sprint 5 — the
            // PostgREST 1000-row cap silently truncated the street fetch):
            // count every drawn street layer and remember each street's colour.
            // Testing/diagnostics only — never read by app logic.
            let renderedSegments = 0
            const renderedStreetColors: Record<string, string> = {}

            features.forEach((feature, index) => {
              const hue = getDistrictHue(index)
              const lineColor = `hsl(${hue}, 65%, 42%)`
              const lines = linesByDistrict.get(feature.id) ?? []
              if (lines.length === 0) return

              const districtGroup = L.featureGroup()

              lines.forEach((sl) => {
                const geom = sl.linestring_geojson as unknown as GeoJSON.GeoJsonObject
                if (sl.is_fallback_point) {
                  // No OSM line for this VZN street → render its geocode point as
                  // a small dot in the district colour (so no street is missing).
                  const g = sl.linestring_geojson as { type?: string; coordinates?: [number, number] }
                  if (g?.type === 'Point' && g.coordinates) {
                    const [lon, lat] = g.coordinates
                    L.circleMarker([lat, lon], {
                      radius: 4,
                      fillColor: lineColor,
                      color: `hsl(${hue}, 70%, 28%)`,
                      weight: 1,
                      fillOpacity: 0.9,
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      pane: 'districts' as any,
                    })
                      .bindTooltip(`${sl.street} (bez OSM línie)`, { sticky: true })
                      .addTo(districtGroup)
                    renderedSegments++
                    renderedStreetColors[sl.street] = lineColor
                  }
                  return
                }
                const layer = L.geoJSON(geom, {
                  style: {
                    color: lineColor,
                    weight: STREET_WEIGHT_DEFAULT,
                    opacity: 0.9,
                  },
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  pane: 'districts' as any,
                })
                layer.bindTooltip(`${feature.name}<br/>${sl.street}`, { sticky: true })
                layer.addTo(districtGroup)
                renderedSegments++
                renderedStreetColors[sl.street] = lineColor
              })

              // Selecting/tapping a district's streets highlights them + opens the
              // district summary popup (the popup's detail link opens /districts/[id]).
              districtGroup.bindPopup(
                buildDistrictSummaryPopup(
                  feature.name,
                  feature.id,
                  districtSummaries[feature.id],
                  feature.composition_color
                ),
                { maxWidth: 280, autoPan: true, autoPanPadding: [20, 20] }
              )
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              districtGroup.on('click', (e: any) => {
                L.DomEvent.stopPropagation(e)
                selectDistrict(feature.id)
                districtGroup.openPopup(e.latlng)
              })
              districtGroup.on('popupclose', () => {
                if (selectedDistrictIdRef.current === feature.id) clearSelection()
              })

              districtGroup.addTo(districtsGroup)
              newDistrictLayersMap.set(feature.id, districtGroup)
            })

            districtLayersRef.current = newDistrictLayersMap

            // E2E hooks (tests/e2e/street-coverage.e2e.mjs): segment count on
            // the map container, per-street colour on window.
            containerRef.current?.setAttribute('data-street-segments', String(renderedSegments))
            ;(window as unknown as { __soStreetColors?: Record<string, string> }).__soStreetColors =
              renderedStreetColors
          }

          // (B) School markers as divIcon SVG (founder-coloured pins).
          const districtLinkedSchoolNames = new Set(
            features.filter((f) => f.school_name).map((f) => f.school_name!)
          )
          const schoolsGroup = L.featureGroup()
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
              // Clicking a school pin highlights its district's streets too.
              .on('click', () => {
                if (drawDemoRef.current) drawDemoRef.current({ id: feature.id })
              })
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

          // (C) MRK localities — point markers (Atlas MRK). OFF by default.
          const mrkGroup = L.featureGroup()
          mrkLocalities.forEach((loc) => {
            const geom = loc.geom_geojson as { type?: string; coordinates?: [number, number] } | null
            if (!geom || geom.type !== 'Point' || !geom.coordinates) return
            const [lon, lat] = geom.coordinates
            L.circleMarker([lat, lon], {
              radius: 5,
              fillColor: '#7c3aed',
              color: '#4c1d95',
              weight: 1.5,
              fillOpacity: 0.85,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'mrk' as any,
            })
              .bindTooltip(
                'MRK lokalita (Atlas MRK) — budova/lokalita marginalizovanej rómskej komunity',
                { sticky: true }
              )
              .addTo(mrkGroup)
          })

          // (D) Per-house address points — VZN house geocodes, district-hued.
          // OFF by default; auto-zooms in on toggle and only renders past the
          // legibility threshold so the toggle never paints an illegible blob.
          const housePointsGroup = L.featureGroup()
          housePoints.forEach((hp) => {
            if (hp.lat == null || hp.lon == null) return
            if (hp.valid === false) return
            const distIdx = districtIndexMap.get(hp.district_id) ?? 0
            const hue = getDistrictHue(distIdx)
            // Demo evidence points (is_demo, from the Checkpoint-1 view flag)
            // get a distinct amber ring so seeded § 44 scenario addresses read
            // as illustration, not real geocode data — data-driven, not a
            // client-side finding.
            const marker = L.circleMarker([hp.lat, hp.lon], hp.is_demo
              ? {
                  radius: 6,
                  fillColor: `hsl(${hue}, 70%, 45%)`,
                  color: '#b45309',
                  weight: 2.5,
                  dashArray: '3,2',
                  fillOpacity: 0.95,
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  pane: 'streetPoints' as any,
                }
              : {
                  radius: 4,
                  fillColor: `hsl(${hue}, 70%, 45%)`,
                  color: `hsl(${hue}, 70%, 25%)`,
                  weight: 1,
                  fillOpacity: 0.9,
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  pane: 'streetPoints' as any,
                })
            marker.bindTooltip(
              `${hp.street} ${hp.house_number}${hp.formatted_address ? `<br/>${hp.formatted_address}` : ''}${hp.partial_match ? ' ⚠ partial match' : ''}${hp.is_demo ? '<br/><strong>Ukážkové (DEMO) dáta</strong> — ilustrácia scenára, nevstupuje do zákonného verdiktu.' : ''}`,
              { sticky: true }
            )
            marker.addTo(housePointsGroup)
          })

          let housePointsEnabled = false
          // Programmatic add/removeLayer below re-fires the layers-control
          // overlayadd/overlayremove synchronously; without this guard,
          // toggling from zoom < 16 removed the layer while the auto-zoom was
          // still in flight, whose overlayremove reset housePointsEnabled and
          // the dots never appeared (docs/ISSUES.md #1). Only USER toggles may
          // flip housePointsEnabled.
          let syncingHousePoints = false
          const updateHousePointsVisibility = () => {
            const z = map.getZoom()
            syncingHousePoints = true
            try {
              if (housePointsEnabled && z >= HOUSE_DOTS_MIN_ZOOM) {
                if (!map.hasLayer(housePointsGroup)) map.addLayer(housePointsGroup)
              } else {
                if (map.hasLayer(housePointsGroup)) map.removeLayer(housePointsGroup)
              }
            } finally {
              syncingHousePoints = false
            }
          }
          map.on('zoomend', updateHousePointsVisibility)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          map.on('overlayadd', (e: any) => {
            if (e.layer === housePointsGroup && !syncingHousePoints) {
              housePointsEnabled = true
              if (map.getZoom() < HOUSE_DOTS_MIN_ZOOM) map.setZoom(HOUSE_DOTS_MIN_ZOOM)
              updateHousePointsVisibility()
            }
          })
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          map.on('overlayremove', (e: any) => {
            if (e.layer === housePointsGroup && !syncingHousePoints) {
              housePointsEnabled = false
              updateHousePointsVisibility()
            }
          })

          // (D2) VLA-14 — uncovered streets (coverage gaps), engine-classified.
          //   vzn_gap — red dashed: real Š1-family § 44 finding (street in the
          //             register, assigned by no VZN); dashed so it can never
          //             be mistaken for a district's assigned street.
          // VLA-20: the gray data_gap ("nedostatočné dáta") state was removed
          // from the product — the engine no longer emits it.
          // Category, evidence text and counts come from so_street_coverage_gaps
          // rows written by engine/coverage_gaps.py — nothing is derived here.
          const GAP_STYLES = {
            vzn_gap: { color: '#dc2626', weight: 3, dashArray: '7,7', opacity: 0.9, className: 'so-gap-vzn' },
          } as const
          const coverageGapsGroup = L.featureGroup()
          let vznGapCount = 0
          const gapCategories: Record<string, string> = {}
          coverageGaps.forEach((gap) => {
            vznGapCount++
            gapCategories[gap.street] = gap.category
            // Streets with no OSM line stay counted (summary strip) but have
            // nothing to draw (e.g. register street whose OSM name differs).
            if (!gap.geom_geojson) return
            const title = 'VZN medzera — ulica bez obvodu'
            const badgeStyle = 'background:#fef2f2;color:#b91c1c;border:1px solid #fecaca'
            const evidenceRows =
              `<li>Register adries: ${gap.in_register ? `áno (${gap.register_address_count} obývateľných adries)` : 'nie'}</li>` +
              `<li>VZN priradenie: ${gap.in_vzn ? 'áno' : 'žiadne'}</li>` +
              `<li>OSM línia: ${gap.has_osm_line ? 'áno' : 'nie'}</li>`
            const popupHtml =
              `<div style="font-size:12px;line-height:1.45;max-width:250px">` +
              `<strong>${gap.street}</strong><br/>` +
              `<span style="display:inline-block;margin:3px 0;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;${badgeStyle}">${title}</span>` +
              `<p style="margin:4px 0">${gap.reason_sk}</p>` +
              `<ul style="margin:4px 0 0;padding-left:16px;color:#4b5563">${evidenceRows}</ul>` +
              `</div>`
            const layer = L.geoJSON(gap.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: GAP_STYLES.vzn_gap,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'districts' as any,
            })
            layer.bindTooltip(`${gap.street} — ${title}`, { sticky: true })
            layer.bindPopup(popupHtml, { maxWidth: 270, autoPan: true, autoPanPadding: [20, 20] })
            layer.addTo(coverageGapsGroup)
          })

          // (D3) VLA-20 — barriers (input table). The seeded railway is
          // FICTIONAL (is_demo) — the tooltip/popup always carry the DEMO
          // badge; the line style is distinct from streets and gap dashes.
          const barriersGroup = L.featureGroup()
          barriers.forEach((barrier) => {
            if (!barrier.geom_geojson) return
            const demoBadge = barrier.is_demo
              ? `<span style="display:inline-block;margin:3px 4px 3px 0;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;background:#fef3c7;color:#b45309;border:1px solid #fcd34d">DEMO</span>`
              : ''
            const popupHtml =
              `<div style="font-size:12px;line-height:1.45;max-width:250px">` +
              `<strong>${barrier.name}</strong><br/>` +
              demoBadge +
              `<span style="display:inline-block;margin:3px 0;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe">Bariéra — ${barrier.kind === 'railway' ? 'železnica' : 'cesta'}</span>` +
              (barrier.reason_sk ? `<p style="margin:4px 0">${barrier.reason_sk}</p>` : '') +
              `</div>`
            const layer = L.geoJSON(barrier.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: { color: '#7c2d12', weight: 4, dashArray: '12,6', opacity: 0.85, className: 'so-barrier' },
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'districts' as any,
            })
            layer.bindTooltip(
              `${barrier.name}${barrier.is_demo ? ' — DEMO' : ''}`,
              { sticky: true }
            )
            layer.bindPopup(popupHtml, { maxWidth: 270, autoPan: true, autoPanPadding: [20, 20] })
            layer.addTo(barriersGroup)
          })

          // E2E hooks (tests/e2e/coverage-gaps.e2e.mjs): counts on the map
          // container + street→category map on window. Testing only.
          containerRef.current?.setAttribute('data-vzn-gaps', String(vznGapCount))
          containerRef.current?.setAttribute('data-barriers', String(barriers.length))
          ;(window as unknown as { __soGapCategories?: Record<string, string> }).__soGapCategories =
            gapCategories

          // (E) Layer control. Default ON: street networks + school pins +
          // coverage gaps (holes must always be explained). Every analytical
          // overlay (MRK, address dots) stays OFF by default.
          const overlays: Record<string, unknown> = {}
          overlays[`Ulice obvodov (${features.length} obvodov)`] = districtsGroup
          overlays[`Školy (${schools.length})`] = schoolsGroup
          if (coverageGaps.length > 0) {
            overlays[`Nepokryté ulice (${vznGapCount} VZN medzera)`] = coverageGapsGroup
          }
          if (barriers.length > 0) {
            overlays[`Bariéry (${barriers.length}, DEMO)`] = barriersGroup
          }
          if (mrkLocalities.length > 0) {
            overlays[`MRK lokality — body (${mrkLocalities.length}, Atlas MRK)`] = mrkGroup
          }
          const validHousePointsCount = housePoints.filter((hp) => hp.valid !== false).length
          if (validHousePointsCount > 0) {
            overlays[`Adresné body obvodov (${validHousePointsCount}, priblížte ≥ ${HOUSE_DOTS_MIN_ZOOM})`] = housePointsGroup
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const layersControl = L.control.layers(undefined, overlays as any, {
            collapsed: layerControlCollapsed(),
          }).addTo(map)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const layersToggle = (layersControl as any)._container?.querySelector(
            '.leaflet-control-layers-toggle'
          ) as HTMLElement | null
          if (layersToggle) {
            layersToggle.setAttribute('title', 'Vrstvy mapy')
            layersToggle.setAttribute('aria-label', 'Vrstvy mapy')
          }

          districtsGroup.addTo(map)
          schoolsGroup.addTo(map)
          coverageGapsGroup.addTo(map)
          barriersGroup.addTo(map)

          const fitToDistricts = () => {
            try {
              const bounds = districtsGroup.getBounds()
              if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [20, 20] })
                return
              }
            } catch { /* fall through */ }
            map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
          }
          fitToDistricts()

          // Home / reset-view: default extent + default layers, clear selection.
          const allOverlayGroups = [mrkGroup, housePointsGroup]
          homeResetRef.current = () => {
            if (clearDemoRef.current) clearDemoRef.current()
            else { try { map.closePopup() } catch { /* ignore */ } }
            allOverlayGroups.forEach((g) => { if (map.hasLayer(g)) map.removeLayer(g) })
            housePointsEnabled = false
            if (!map.hasLayer(districtsGroup)) districtsGroup.addTo(map)
            if (!map.hasLayer(schoolsGroup)) schoolsGroup.addTo(map)
            if (!map.hasLayer(coverageGapsGroup)) coverageGapsGroup.addTo(map)
            if (!map.hasLayer(barriersGroup)) barriersGroup.addTo(map)
            fitToDistricts()
          }

          layersRef.current.psk = [districtsGroup, schoolsGroup, coverageGapsGroup, mrkGroup, housePointsGroup, barriersGroup]
        } else {
          const [districtsGroup, schoolsGroup, coverageGapsGroup, , , barriersGroup] = layersRef.current.psk
          districtsGroup.addTo(map)
          schoolsGroup.addTo(map)
          if (coverageGapsGroup) coverageGapsGroup.addTo(map)
          if (barriersGroup) barriersGroup.addTo(map)
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
      {/* Map controls. "← Späť na Slovensko" only makes sense in PSK detail mode.
          The Home button is ALWAYS visible and ALWAYS returns framed to Prešov
          from ANY state (item 8c): in SK overview it switches back to PSK mode
          (which re-frames on the districts); in PSK mode it runs the full reset
          (default extent + default layers + cleared selection). */}
      <div className="absolute top-2 left-2 z-[1000] flex items-center gap-2">
        {mode === 'psk' && (
          <button
            onClick={() => setMode('sk')}
            className="rounded-sm bg-white border border-gov-border px-3 py-1.5 text-xs font-medium shadow-gov hover:bg-gov-blue50 transition-colors"
            aria-label="Späť na prehľad Slovenska"
          >
            ← Späť na Slovensko
          </button>
        )}
        {/* Item 8c / item 13 — Home / reset view: always frames Prešov. */}
        <button
          onClick={() => {
            if (mode !== 'psk') {
              // From SK overview: switch to PSK detail; the mode effect re-frames
              // on the districts (reliable open-on-Prešov).
              setMode('psk')
              if (mapRef.current) mapRef.current.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
              return
            }
            if (homeResetRef.current) homeResetRef.current()
            // Fallback: the PSK-mode effect assigns homeResetRef async; if the
            // user clicks before it runs, still reset the view directly so the
            // button never silently no-ops.
            else if (mapRef.current) mapRef.current.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
          }}
          className="inline-flex h-[30px] w-[30px] items-center justify-center rounded-sm bg-white border border-gov-border shadow-gov hover:bg-gov-blue50 transition-colors"
          aria-label="Obnoviť pôvodné zobrazenie mapy (Prešov)"
          title="Obnoviť pôvodné zobrazenie (Prešov)"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#0055A0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 10.5 12 3l9 7.5" />
            <path d="M5 9.5V21h14V9.5" />
          </svg>
        </button>
      </div>
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
