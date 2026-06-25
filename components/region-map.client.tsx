'use client'

import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoPskMunicipality, SoDistrictGeocodedGeom, SoStreetGeocode } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, SK_CENTER, SK_DEFAULT_ZOOM, PSK_KRAJ_NAMES, COMPOSITION_COLOR_MAP, getDistrictHue } from '@/lib/config/region'

interface RegionMapClientProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  findings: SoFindingsPanelItem[]
  overlaps?: SoDistrictOverlap[]
  municipalities?: SoPskMunicipality[]
  geocodedGeom?: SoDistrictGeocodedGeom[]
  streetGeocodes?: SoStreetGeocode[]
  initialMode?: 'sk' | 'psk'
}

function isPskKraj(name: string): boolean {
  const lower = name.toLowerCase()
  return PSK_KRAJ_NAMES.some((n) => lower.includes(n.toLowerCase()))
}

export function RegionMapClient({ features, schools, mrkOverlays, overlaps = [], municipalities = [], geocodedGeom = [], streetGeocodes = [], initialMode = 'sk' }: RegionMapClientProps) {
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
                { collapsed: false }
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
                  weight: 2.5,
                  fillColor: `hsl(${hue}, 65%, 60%)`,
                  fillOpacity: 0, // borders-only by default
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
                geoJsonLayer.setStyle({ weight: 4 })
              })
              geoJsonLayer.on('mouseout', () => {
                geoJsonLayer.setStyle({ weight: 2.5 })
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

          // (B-heatmap) Overlap polygons — multiply blend mode applied on the pane itself
          // Each overlap polygon is a light red with no border; stacking = visual darkening
          const overlapsGroup = L.featureGroup()

          overlaps.forEach((overlap) => {
            if (!overlap.overlap_geojson) return
            const geoJsonLayer = L.geoJSON(overlap.overlap_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: {
                fillColor: '#dc2626',
                fillOpacity: 0.10,
                color: 'transparent',
                weight: 0,
              },
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              pane: 'overlaps' as any,
            })
            geoJsonLayer.bindTooltip(
              `Prekryv obvodov: ${overlap.district_a_name} × ${overlap.district_b_name}<br/>Plocha: ${(overlap.overlap_area_m2 / 10000).toFixed(2)} ha<br/><em>1 prekryv (2 obvody)</em>`,
              { sticky: true }
            )
            geoJsonLayer.addTo(overlapsGroup)
          })

          // (G) Google-geocoded hull layer
          const googleHullGroup = L.featureGroup()
          geocodedGeom.forEach((g) => {
            if (!g.geom_geojson) return
            const layer = L.geoJSON(g.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: {
                fillColor: 'transparent',
                color: '#10b981',
                weight: 2.5,
                dashArray: '6 3',
              },
            })
            const meta = g.geom_google_metadata
            const pts = meta?.ok_points ?? '?'
            const partial = meta?.partial_match_points ?? 0
            layer.bindTooltip(
              `<strong>${g.name}</strong><br/>Google hull (Sprint G)<br/>${pts} adresných bodov${partial ? `, ${partial} partial match` : ''}`,
              { sticky: true }
            )
            layer.addTo(googleHullGroup)
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

          // Layer control — overlaps OFF by default (visually heavy)
          L.control.layers(
            undefined,
            {
              'Obvody (12)': districtsGroup,
              'Google Geocoded hull (Sprint G)': googleHullGroup,
              'Adresy z VZN (Google)': streetPointsGroup,
              'Prekryvy obvodov': overlapsGroup,
              'MRK lokality': mrkGroup,
              'Školy (26)': schoolsGroup,
            },
            { collapsed: false }
          ).addTo(map)

          // Only add overlapsGroup if it has content, but OFF by default = don't addTo(map)
          districtsGroup.addTo(map)
          // Google layers — ON by default so Vlado sees comparison immediately
          googleHullGroup.addTo(map)
          streetPointsGroup.addTo(map)
          // overlapsGroup is NOT added — user enables from layer control
          mrkGroup.addTo(map)
          schoolsGroup.addTo(map)

          layersRef.current.psk = [districtsGroup, schoolsGroup, mrkGroup, overlapsGroup, googleHullGroup, streetPointsGroup]
        } else {
          const [districtsGroup, schoolsGroup, mrkGroup, , googleHullGroup, streetPointsGroup] = layersRef.current.psk
          // Re-add active layers (not overlapsGroup by default)
          districtsGroup.addTo(map)
          schoolsGroup.addTo(map)
          mrkGroup.addTo(map)
          if (googleHullGroup) googleHullGroup.addTo(map)
          if (streetPointsGroup) streetPointsGroup.addTo(map)
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
