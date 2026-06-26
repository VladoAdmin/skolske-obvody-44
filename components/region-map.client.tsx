'use client'

import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoDistrictIsland, SoPskMunicipality, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi, SoDistrictCleanGeom, SoHouseDot } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, SK_CENTER, SK_DEFAULT_ZOOM, PSK_KRAJ_NAMES, COMPOSITION_COLOR_MAP, getDistrictHue } from '@/lib/config/region'

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
  initialMode?: 'sk' | 'psk'
}

function isPskKraj(name: string): boolean {
  const lower = name.toLowerCase()
  return PSK_KRAJ_NAMES.some((n) => lower.includes(n.toLowerCase()))
}

export function RegionMapClient({ features, schools, mrkOverlays, overlaps = [], islands = [], municipalities = [], streetGeocodes = [], housePoints = [], voronoiGeom = [], cleanGeom = [], houseDots = [], initialMode = 'sk' }: RegionMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layersRef = useRef<{ sk?: any; psk?: any }>({})
  // Per-district layer map: id -> L.GeoJSON layer
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const districtLayersRef = useRef<Map<string, any>>(new Map())
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
      const districtPane = map.createPane('districts')
      districtPane.style.zIndex = '450'
      const mrkPane = map.createPane('mrk')
      mrkPane.style.zIndex = '460'
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
            layer.setStyle({ fillOpacity: 0.4, fillColor: `hsl(${hue}, 65%, 60%)` })
            try {
              const bounds = layer.getBounds()
              if (bounds.isValid()) {
                map.flyToBounds(bounds, { padding: [30, 30], duration: 1 })
              }
            } catch { /* ignore */ }
          } else {
            layer.setStyle({ fillOpacity: 0 })
          }
        })
      }
      window.addEventListener('so:select-district', selectDistrictHandler)

      return () => {
        window.removeEventListener('so:flyto', flyToHandler)
        window.removeEventListener('so:toggle-district', toggleDistrictHandler)
        window.removeEventListener('so:select-district', selectDistrictHandler)
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
            features.forEach((feature, index) => {
              if (!feature.geom_geojson) return

              const hue = getDistrictHue(index)
              const borderColor = `hsl(${hue}, 65%, 45%)`

              const geoJsonLayer = L.geoJSON(feature.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
                style: {
                  color: borderColor,
                  weight: 3,
                  fillColor: `hsl(${hue}, 65%, 60%)`,
                  fillOpacity: 0.2, // sýta per-district fill
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
                geoJsonLayer.setStyle({ weight: 5 })
              })
              geoJsonLayer.on('mouseout', () => {
                geoJsonLayer.setStyle({ weight: 3 })
              })

              geoJsonLayer.on('click', () => {
                router.push(`/districts/${feature.id}`)
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

          const makeSchoolIcon = (size: number) => L.divIcon({
            html: `<div style="line-height:0"><svg viewBox="0 0 24 24" width="${size}" height="${size}"><circle cx="12" cy="12" r="10" fill="#2563eb" stroke="#fff" stroke-width="2"/><text x="12" y="16" text-anchor="middle" fill="#fff" font-size="12" font-weight="700">Š</text></svg></div>`,
            className: 'school-icon',
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
          })

          features.forEach((feature) => {
            if (!feature.school_geom_geojson) return
            const geom = feature.school_geom_geojson as { type: string; coordinates: [number, number] }
            if (geom.type !== 'Point') return
            const [lon, lat] = geom.coordinates
            L.marker([lat, lon], {
              icon: makeSchoolIcon(22),
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'schools' as any,
            })
              .bindTooltip(feature.school_name ?? 'Škola')
              .addTo(schoolsGroup)
          })

          schools.forEach((school) => {
            if (!school.geom_geojson) return
            if (districtLinkedSchoolNames.has(school.name)) return
            const geom = school.geom_geojson as { type: string; coordinates: [number, number] }
            if (geom.type !== 'Point') return
            const [lon, lat] = geom.coordinates
            L.marker([lat, lon], {
              icon: makeSchoolIcon(16),
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'schools' as any,
            })
              .bindTooltip(`${school.name}${school.kind ? ` (${school.kind})` : ''}`)
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
              },
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'mrk' as any,
            })
            geoJsonLayer.bindTooltip(
              `<strong>MRK: ${mrk.name ?? 'Lokalita'}</strong>${mrk.severity_class ? `<br/>Kategória: ${mrk.severity_class}` : ''}`,
              { sticky: true }
            )
            geoJsonLayer.addTo(mrkGroup)
          })

          mrkGroup.addTo(map)

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

          // Zoom-gated visibility for house dots. The listener is registered
          // once per PSK build; it's safe to call addLayer/removeLayer
          // repeatedly because Leaflet ignores no-op adds.
          const updateHouseDotsVisibility = () => {
            const z = map.getZoom()
            if (z >= HOUSE_DOTS_MIN_ZOOM) {
              if (!map.hasLayer(houseDotsGroup)) map.addLayer(houseDotsGroup)
            } else {
              if (map.hasLayer(houseDotsGroup)) map.removeLayer(houseDotsGroup)
            }
          }
          map.on('zoomend', updateHouseDotsVisibility)

          // Layer control — MVP demo view. The "Obvody" layer is the new
          // clean geom from Sprint M-2 (smoothed polygons) when present;
          // the original Sprint A geom is exposed as an optional toggle so
          // analysts can compare the two surfaces. Voronoi remains engine
          // input only and is hidden from the user-facing control.
          const hasCleanGeom = cleanGeom.length > 0
          const overlays: Record<string, unknown> = {}
          if (hasCleanGeom) {
            overlays[`Obvody (${cleanGeom.length})`] = cleanGroup
            overlays[`Obvody — VZN hull (Sprint A, ${features.length})`] = districtsGroup
          } else {
            overlays[`Obvody (${features.length})`] = districtsGroup
          }
          overlays[`Školy (${schools.length})`] = schoolsGroup
          overlays['Prekryvy obvodov (kde 2+ obvodov hovorí o tej istej adrese)'] = overlapsGroup
          const anomalyIslandsCount = islands.filter(
            (i) => i.anomaly_type != null || i.status === 'unresolved_anomaly' || i.is_demo === true
          ).length
          if (anomalyIslandsCount > 0) {
            overlays[`Anomálie / ostrovy (${anomalyIslandsCount})`] = islandsGroup
          }
          overlays['MRK lokality (Atlas marginalizovaných rómskych komunít)'] = mrkGroup
          overlays['Domy z VZN (Google geokódovanie, 460 platných)'] = housePointsGroup
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

          // Default ON: clean obvody (or fallback to Sprint A) + školy + prekryvy.
          if (hasCleanGeom) {
            cleanGroup.addTo(map)
          } else {
            districtsGroup.addTo(map)
          }
          schoolsGroup.addTo(map)
          if (overlaps.length > 0) overlapsGroup.addTo(map)
          if (anomalyIslandsCount > 0) islandsGroup.addTo(map)
          // House dots: register zoom-gated visibility now (no-op if zoom < threshold)
          updateHouseDotsVisibility()

          // Prefer fitting bounds to the cleanGroup if it exists, otherwise the
          // legacy districtsGroup.
          try {
            const primary = hasCleanGeom ? cleanGroup : districtsGroup
            const bounds = primary.getBounds()
            if (bounds.isValid()) {
              map.fitBounds(bounds, { padding: [20, 20] })
            }
          } catch {
            map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
          }

          layersRef.current.psk = [districtsGroup, schoolsGroup, mrkGroup, overlapsGroup, streetPointsGroup, housePointsGroup, voronoiGroup, cleanGroup, houseDotsGroup, islandsGroup]
        } else {
          const [districtsGroup, schoolsGroup, , overlapsGroup, , , , cleanGroupCached, houseDotsGroupCached, islandsGroupCached] = layersRef.current.psk
          const hasCleanGeom = cleanGeom.length > 0
          // Re-add active layers (obvody + školy + prekryvy ON by default)
          if (hasCleanGeom && cleanGroupCached) {
            cleanGroupCached.addTo(map)
          } else {
            districtsGroup.addTo(map)
          }
          schoolsGroup.addTo(map)
          if (overlaps.length > 0) overlapsGroup.addTo(map)
          if (islandsGroupCached) islandsGroupCached.addTo(map)
          // House dots: gated re-add by current zoom
          if (houseDotsGroupCached && map.getZoom() >= HOUSE_DOTS_MIN_ZOOM) {
            houseDotsGroupCached.addTo(map)
          }
          if (features.length > 0) {
            try {
              const primary = hasCleanGeom && cleanGroupCached ? cleanGroupCached : districtsGroup
              const bounds = primary.getBounds()
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
