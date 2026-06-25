'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import type { DistrictMapFeature } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, COMPOSITION_COLOR_MAP } from '@/lib/config/region'

interface RegionMapClientProps {
  features: DistrictMapFeature[]
}

export function RegionMapClient({ features }: RegionMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    // Dynamically import leaflet to avoid SSR issues
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
        center: PSK_CENTER,
        zoom: PSK_DEFAULT_ZOOM,
      })

      mapRef.current = map

      // OSM tile layer with mandatory attribution
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom: 19,
      }).addTo(map)

      if (features.length === 0) {
        // No features — show info only
        return
      }

      // Add district polygons
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

        geoJsonLayer.addTo(map)
      })

      // Add school markers
      features.forEach((feature) => {
        if (!feature.school_geom_geojson) return
        const geom = feature.school_geom_geojson as { type: string; coordinates: [number, number] }
        if (geom.type !== 'Point') return
        const [lon, lat] = geom.coordinates
        L.marker([lat, lon])
          .bindTooltip(feature.school_name ?? 'Škola')
          .addTo(map)
      })
    }).catch(console.error)

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
    // features is stable from SSR — safe to include
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      role="application"
      aria-label="Interaktívna mapa školských obvodov Prešova"
      aria-describedby="map-fallback-table"
      tabIndex={0}
    />
  )
}
