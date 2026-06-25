'use client'

import { useEffect, useRef } from 'react'
import type { DistrictMapFeature } from '@/lib/supabase/types'
import { COMPOSITION_COLOR_MAP } from '@/lib/config/region'

interface DistrictMiniMapClientProps {
  feature: DistrictMapFeature | null
}

export function DistrictMiniMapClient({ feature }: DistrictMiniMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    import('leaflet').then((L) => {
      if (!containerRef.current || mapRef.current) return

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-shadow.png',
      })

      const map = L.map(containerRef.current!, { zoom: 13, zoomControl: true })
      mapRef.current = map

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom: 19,
      }).addTo(map)

      if (feature?.geom_geojson) {
        const colorConfig = COMPOSITION_COLOR_MAP[feature.composition_color] ?? COMPOSITION_COLOR_MAP.NONE
        const layer = L.geoJSON(feature.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
          style: {
            color: colorConfig.stroke,
            weight: 2,
            fillColor: colorConfig.fill,
            fillOpacity: colorConfig.fillOpacity,
          },
        }).addTo(map)
        map.fitBounds(layer.getBounds(), { padding: [20, 20] })
      } else {
        // Default center on Prešov
        map.setView([49.0, 21.24], 13)
      }

      // School marker
      if (feature?.school_geom_geojson) {
        const geom = feature.school_geom_geojson as { type: string; coordinates: [number, number] }
        if (geom.type === 'Point') {
          const [lon, lat] = geom.coordinates
          L.marker([lat, lon])
            .bindTooltip(feature.school_name ?? 'Škola')
            .addTo(map)
        }
      }
    }).catch(console.error)

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
  }, [feature])

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      role="application"
      aria-label="Mini mapa školského obvodu"
      tabIndex={0}
    />
  )
}
