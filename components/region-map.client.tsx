'use client'

import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoDistrictIsland, SoPskMunicipality, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi, SoDistrictCleanGeom, SoHouseDot } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, SK_CENTER, SK_DEFAULT_ZOOM, PSK_KRAJ_NAMES, COMPOSITION_COLOR_MAP, getDistrictHue } from '@/lib/config/region'
import { buildDistrictSchoolPopup, buildDistrictSummaryPopup, buildNonVznSchoolPopup, type DistrictPopupSummary } from '@/lib/compliance/school-popup'

// Zoom threshold (inclusive) at which per-house dots become visible.
const HOUSE_DOTS_MIN_ZOOM = 16

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
        const { lat, lon, zoom } = (e as CustomEvent<{ lat: number; lon: number; zoom?: number }>).detail
        map.flyTo([lat, lon], zoom ?? 15, { duration: 1 })
      }
      window.addEventListener('so:flyto', flyToHandler)

      // --- CustomEvent: toggle individual district visibility ---
      const toggleDistrictHandler = (e: Event) => {
        const { id, visible } = (e as CustomEvent<{ id: string; visible: boolean }>).detail
        const layer = districtLayersRef.current.get(id)
        if (!layer) return
        if (visible) {
          map.addLayer(layer)
        } else {
          map.removeLayer(layer)
        }
      }
      window.addEventListener('so:toggle-district', toggleDistrictHandler)

      // --- CustomEvent: select district (highlight + flyTo centroid) ---
      const selectDistrictHandler = (e: Event) => {
        const { id } = (e as CustomEvent<{ id: string }>).detail
        districtLayersRef.current.forEach((layer, layerId) => {
          const featureIndex = features.findIndex((f) => f.id === layerId)
          const hue = getDistrictHue(featureIndex >= 0 ? featureIndex : 0)
          if (layerId === id) {
            layer.setStyle({ weight: 4.5, fillOpacity: 0.55, fillColor: `hsl(${hue}, 65%, 55%)` })
            layer.bringToFront()
            try {
              const bounds = layer.getBounds()
              if (bounds.isValid()) {
                map.flyToBounds(bounds, { padding: [30, 30], duration: 1 })
              }
            } catch { /* ignore */ }
          } else {
            // restore the solid-fill default (distinct palette colour)
            layer.setStyle({ weight: 2.5, fillOpacity: 0.40 })
          }
        })
      }
      window.addEventListener('so:select-district', selectDistrictHandler)

      // --- CustomEvent: draw a route line for distance findings (Pa/Pb) ---
      // Draws a dashed line from the district centroid (representative address
      // area) to the school location so the user can see the problematic
      // air-line distance visually. Replaces any previous route layer.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let routeLayer: any = null
      const drawRouteHandler = (e: Event) => {
        const { from, to, label } = (e as CustomEvent<{
          districtId: string
          from: { lat: number; lon: number }
          to: { lat: number; lon: number }
        } & { label?: string }>).detail
        // Remove previous route if any
        if (routeLayer) {
          map.removeLayer(routeLayer)
          routeLayer = null
        }
        const fromLatLng: [number, number] = [from.lat, from.lon]
        const toLatLng: [number, number] = [to.lat, to.lon]
        // Compute straight-line distance in metres (Haversine via Leaflet)
        const distM = map.distance(fromLatLng, toLatLng)
        const distKm = (distM / 1000).toFixed(2)
        routeLayer = L.polyline([fromLatLng, toLatLng], {
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
        routeLayer.openPopup()
      }
      window.addEventListener('so:draw-route', drawRouteHandler)

      return () => {
        window.removeEventListener('so:flyto', flyToHandler)
        window.removeEventListener('so:toggle-district', toggleDistrictHandler)
        window.removeEventListener('so:select-district', selectDistrictHandler)
        window.removeEventListener('so:draw-route', drawRouteHandler)
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

            // Tapping the empty map (outside any polygon) clears the highlight.
            map.on('click', resetSelectedDistrict)

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
                geoJsonLayer.openPopup(e.latlng)
              })

              // Closing the popup clears the highlight (unless another district
              // was selected in the meantime).
              geoJsonLayer.on('popupclose', () => {
                if (selectedDistrictIdRef.current === feature.id) {
                  geoJsonLayer.setStyle({ weight: WEIGHT_DEFAULT, fillOpacity: FILL_OPACITY_DEFAULT })
                  selectedDistrictIdRef.current = null
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
