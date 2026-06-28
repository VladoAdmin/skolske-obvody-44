'use client'

import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'
import type {
  DistrictMapFeature,
  SoSchoolMarker,
  SoHousePoint,
  SoDistrictStreetLine,
} from '@/lib/supabase/types'
import {
  getDistrictHue,
  PSK_CENTER,
  PSK_DEFAULT_ZOOM,
} from '@/lib/config/region'
import { buildDistrictSchoolPopup, buildNonVznSchoolPopup, type DistrictPopupSummary } from '@/lib/compliance/school-popup'

// On mobile (≤767px) the layer control starts collapsed so the legend
// does not obscure the map; it expands into the full checkbox list on tap.
function layerControlCollapsed(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(max-width: 767px)').matches
}

interface DistrictDetailMapClientProps {
  currentDistrictId: string
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  housePoints: SoHousePoint[]
  // Streets pivot: same street source as the main map (single SSOT).
  streetLines: SoDistrictStreetLine[]
  districtSummaries?: Record<string, DistrictPopupSummary>
}

export function DistrictDetailMapClient({
  currentDistrictId,
  features,
  schools,
  housePoints,
  streetLines,
  districtSummaries = {},
}: DistrictDetailMapClientProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    import('leaflet').then((L) => {
      if (!containerRef.current || mapRef.current) return

      // Fix default icon paths
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9/dist/images/marker-shadow.png',
      })

      const map = L.map(containerRef.current!, {
        zoomControl: true,
        minZoom: 10,
        maxZoom: 19,
      })
      mapRef.current = map

      // Panes for z-ordering
      const districtPane = map.createPane('districts')
      districtPane.style.zIndex = '450'
      const schoolsPane = map.createPane('schools')
      schoolsPane.style.zIndex = '700'
      const streetPointsPane = map.createPane('streetPoints')
      streetPointsPane.style.zIndex = '680'

      // OSM tile layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom: 19,
        noWrap: true,
      }).addTo(map)

      // Stable per-district hue (same palette as the main map).
      const districtIndexMap = new Map<string, number>()
      features.forEach((f, idx) => districtIndexMap.set(f.id, idx))

      // --- Streets: the CURRENT district's streets are drawn prominently in its
      // colour; neighbour districts' streets are faint context. SAME rendering as
      // the main map (streets pivot) — no polygons anywhere.
      const linesByDistrict = new Map<string, SoDistrictStreetLine[]>()
      for (const sl of streetLines) {
        if (!sl.linestring_geojson) continue
        const arr = linesByDistrict.get(sl.district_id) ?? []
        arr.push(sl)
        linesByDistrict.set(sl.district_id, arr)
      }

      const currentGroup = L.featureGroup() // selected district (prominent)
      const contextGroup = L.featureGroup() // neighbours (faint)
      let currentBounds: ReturnType<typeof L.latLngBounds> | null = null

      features.forEach((feature, index) => {
        const isCurrent = feature.id === currentDistrictId
        const hue = getDistrictHue(index)
        const lines = linesByDistrict.get(feature.id) ?? []
        if (lines.length === 0) return
        const target = isCurrent ? currentGroup : contextGroup

        lines.forEach((sl) => {
          if (sl.is_fallback_point) {
            const g = sl.linestring_geojson as { type?: string; coordinates?: [number, number] }
            if (g?.type === 'Point' && g.coordinates) {
              const [lon, lat] = g.coordinates
              L.circleMarker([lat, lon], {
                radius: isCurrent ? 4 : 3,
                fillColor: isCurrent ? `hsl(${hue}, 65%, 42%)` : '#94a3b8',
                color: isCurrent ? `hsl(${hue}, 70%, 28%)` : '#64748b',
                weight: 1,
                fillOpacity: isCurrent ? 0.9 : 0.4,
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                pane: 'districts' as any,
              })
                .bindTooltip(`${sl.street} (bez OSM línie)`, { sticky: true })
                .addTo(target)
            }
            return
          }
          const layer = L.geoJSON(sl.linestring_geojson as unknown as GeoJSON.GeoJsonObject, {
            style: isCurrent
              ? { color: `hsl(${hue}, 70%, 38%)`, weight: 4, opacity: 1 }
              : { color: '#94a3b8', weight: 2, opacity: 0.45 },
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            pane: 'districts' as any,
          })
          layer.bindTooltip(`${feature.name}<br/>${sl.street}`, { sticky: true })
          layer.addTo(target)
        })
      })

      // Add context first so the selected district's streets render on top.
      contextGroup.addTo(map)
      currentGroup.addTo(map)
      try {
        const b = currentGroup.getBounds()
        if (b.isValid()) currentBounds = b
      } catch { /* ignore */ }

      if (currentBounds) {
        map.fitBounds(currentBounds, { padding: [30, 30] })
      } else {
        map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
      }

      // --- School markers ---
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
        const isCurrent = feature.id === currentDistrictId
        L.marker([lat, lon], {
          icon: makeSchoolIcon(isCurrent ? 26 : 18),
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          pane: 'schools' as any,
        })
          .bindTooltip(`${schoolName}${isCurrent ? ' (aktuálna)' : ''}`)
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

      const districtLinkedSchoolNames = new Set(
        features.filter((f) => f.school_name).map((f) => f.school_name!)
      )
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

      // --- House points (current district larger) — OFF by default ---
      const housePointsGroup = L.featureGroup()
      housePoints.forEach((hp) => {
        if (hp.lat == null || hp.lon == null) return
        if (hp.valid === false) return
        const isCurrent = hp.district_id === currentDistrictId
        const distIdx = districtIndexMap.get(hp.district_id) ?? 0
        const hue = getDistrictHue(distIdx)
        const marker = L.circleMarker([hp.lat, hp.lon], {
          radius: isCurrent ? 4 : 2,
          fillColor: `hsl(${hue}, 70%, 45%)`,
          color: `hsl(${hue}, 70%, 25%)`,
          weight: isCurrent ? 1 : 0.5,
          fillOpacity: isCurrent ? 0.9 : 0.6,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          pane: 'streetPoints' as any,
        })
        marker.bindTooltip(
          `${hp.street} ${hp.house_number}${hp.formatted_address ? `<br/>${hp.formatted_address}` : ''}${hp.partial_match ? ' ⚠ partial' : ''}`,
          { sticky: true }
        )
        marker.addTo(housePointsGroup)
      })

      // Layer control.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const overlayLayers: Record<string, any> = {
        'Ulice tohto obvodu': currentGroup,
        'Ulice susedných obvodov (kontext)': contextGroup,
        'Školy': schoolsGroup,
        '⚙ Expert: Adresné body (Google geokódovanie)': housePointsGroup,
      }
      const layersControl = L.control.layers(
        undefined,
        overlayLayers,
        { collapsed: layerControlCollapsed() }
      ).addTo(map)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const layersToggle = (layersControl as any)._container?.querySelector(
        '.leaflet-control-layers-toggle'
      ) as HTMLElement | null
      if (layersToggle) {
        layersToggle.setAttribute('title', 'Vrstvy mapy')
        layersToggle.setAttribute('aria-label', 'Vrstvy mapy')
      }
    }).catch(console.error)

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      role="application"
      aria-label="Mapa školského obvodu — ulice"
      tabIndex={0}
    />
  )
}
