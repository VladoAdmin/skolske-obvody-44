'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, SK_CENTER, SK_DEFAULT_ZOOM, PSK_KRAJ_NAMES, COMPOSITION_COLOR_MAP } from '@/lib/config/region'

interface RegionMapClientProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  findings: SoFindingsPanelItem[]
  initialMode?: 'sk' | 'psk'
}

function isPskKraj(name: string): boolean {
  const lower = name.toLowerCase()
  return PSK_KRAJ_NAMES.some((n) => lower.includes(n.toLowerCase()))
}

export function RegionMapClient({ features, schools, mrkOverlays, initialMode = 'sk' }: RegionMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layersRef = useRef<{ sk?: any; psk?: any }>({})
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

      return () => {
        window.removeEventListener('so:flyto', flyToHandler)
      }
    }).catch(console.error)

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        layersRef.current = {}
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
        }

        // Show SK overview layer — load once
        if (!layersRef.current.sk) {
          fetch('/sk-kraje.geojson')
            .then((r) => r.json())
            .then((geojson) => {
              const skGroup = L.featureGroup()

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
          const districtsGroup = L.featureGroup()

          if (features.length > 0) {
            features.forEach((feature) => {
              if (!feature.geom_geojson) return

              const colorConfig = COMPOSITION_COLOR_MAP[feature.composition_color] ?? COMPOSITION_COLOR_MAP.NONE
              const symbol = colorConfig.symbol

              const geoJsonLayer = L.geoJSON(feature.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
                style: {
                  color: colorConfig.stroke,
                  weight: 1.5,
                  fillColor: colorConfig.fill,
                  fillOpacity: colorConfig.fillOpacity,
                },
              })

              geoJsonLayer.bindTooltip(
                `<strong>${feature.name}</strong><br/>${symbol} ${feature.composition_color ?? 'NONE'}${feature.composition_reason ? `<br/><em>${feature.composition_reason}</em>` : ''}`,
                { sticky: true }
              )

              geoJsonLayer.on('click', () => {
                router.push(`/districts/${feature.id}`)
              })

              geoJsonLayer.addTo(districtsGroup)
            })

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

          // School markers
          const districtLinkedSchoolNames = new Set(
            features.filter((f) => f.school_name).map((f) => f.school_name!)
          )

          const schoolsGroup = L.featureGroup()

          features.forEach((feature) => {
            if (!feature.school_geom_geojson) return
            const geom = feature.school_geom_geojson as { type: string; coordinates: [number, number] }
            if (geom.type !== 'Point') return
            const [lon, lat] = geom.coordinates
            L.circleMarker([lat, lon], {
              radius: 5,
              fillColor: '#2563eb',
              color: '#1d4ed8',
              weight: 1,
              fillOpacity: 0.85,
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
            L.circleMarker([lat, lon], {
              radius: 4,
              fillColor: '#60a5fa',
              color: '#2563eb',
              weight: 1,
              fillOpacity: 0.75,
            })
              .bindTooltip(`${school.name}${school.kind ? ` (${school.kind})` : ''}`)
              .addTo(schoolsGroup)
          })

          schoolsGroup.addTo(map)

          // MRK overlays
          const mrkGroup = L.featureGroup()

          mrkOverlays.forEach((mrk) => {
            if (!mrk.geom_geojson) return
            const geoJsonLayer = L.geoJSON(mrk.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
              style: {
                color: '#5b21b6',
                weight: 1.5,
                fillColor: '#7c3aed',
                fillOpacity: 0.15,
              },
            })
            geoJsonLayer.bindTooltip(
              `<strong>MRK: ${mrk.name ?? 'Lokalita'}</strong>${mrk.severity_class ? `<br/>Kategória: ${mrk.severity_class}` : ''}`,
              { sticky: true }
            )
            geoJsonLayer.addTo(mrkGroup)
          })

          mrkGroup.addTo(map)

          // Layer control
          L.control.layers(
            undefined,
            {
              'Obvody': districtsGroup,
              'Školy': schoolsGroup,
              'MRK lokality': mrkGroup,
            },
            { collapsed: false }
          ).addTo(map)

          layersRef.current.psk = [districtsGroup, schoolsGroup, mrkGroup]
        } else {
          layersRef.current.psk.forEach((l: unknown) => (l as { addTo: (m: unknown) => void }).addTo(map))
          if (features.length > 0) {
            const districtsGroup = layersRef.current.psk[0]
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
