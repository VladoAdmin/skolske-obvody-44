'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem } from '@/lib/supabase/types'
import { PSK_CENTER, PSK_DEFAULT_ZOOM, COMPOSITION_COLOR_MAP } from '@/lib/config/region'

interface RegionMapClientProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  findings: SoFindingsPanelItem[]
}

export function RegionMapClient({ features, schools, mrkOverlays }: RegionMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)

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
        center: PSK_CENTER,
        zoom: PSK_DEFAULT_ZOOM,
      })

      mapRef.current = map

      // OSM tile layer with mandatory attribution
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom: 19,
      }).addTo(map)

      // --- District polygon layer ---
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

        // fitBounds to district polygons
        try {
          const bounds = districtsGroup.getBounds()
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [20, 20] })
          }
        } catch {
          // fallback to default center if fitBounds fails
          map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
        }
      }

      districtsGroup.addTo(map)

      // --- School markers layer (circle markers, smaller, blue) ---
      // Include all school markers, deduplicate against district-linked school_geom_geojson
      const districtLinkedSchoolNames = new Set(
        features.filter((f) => f.school_name).map((f) => f.school_name!)
      )

      const schoolsGroup = L.featureGroup()

      // Add district-linked school markers from district features
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

      // Add additional school markers (not linked to districts)
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

      // --- MRK overlay layer (purple polygons) ---
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

      // --- Layer control ---
      L.control.layers(
        undefined,
        {
          'Obvody': districtsGroup,
          'Školy': schoolsGroup,
          'MRK lokality': mrkGroup,
        },
        { collapsed: false }
      ).addTo(map)

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
      }
    }
    // features/schools/mrkOverlays are stable from SSR — safe to omit
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
