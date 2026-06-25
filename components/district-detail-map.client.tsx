'use client'

import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'
import type {
  DistrictMapFeature,
  SoSchoolMarker,
  SoMrkOverlay,
  SoHousePoint,
  SoStreetGeocode,
  SoDistrictVoronoi,
  SoDistrictIsland,
} from '@/lib/supabase/types'
import {
  COMPOSITION_COLOR_MAP,
  getDistrictHue,
  PSK_CENTER,
  PSK_DEFAULT_ZOOM,
} from '@/lib/config/region'

interface DistrictDetailMapClientProps {
  currentDistrictId: string
  features: DistrictMapFeature[]
  voronoiFeatures: SoDistrictVoronoi[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  housePoints: SoHousePoint[]
  streetGeocodes: SoStreetGeocode[]
  islands: SoDistrictIsland[]
}

export function DistrictDetailMapClient({
  currentDistrictId,
  features,
  voronoiFeatures,
  schools,
  mrkOverlays,
  housePoints,
  streetGeocodes,
  islands,
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
      const mrkPane = map.createPane('mrk')
      mrkPane.style.zIndex = '460'
      const schoolsPane = map.createPane('schools')
      schoolsPane.style.zIndex = '700'
      const streetPointsPane = map.createPane('streetPoints')
      streetPointsPane.style.zIndex = '680'
      const islandLabelsPane = map.createPane('islandLabels')
      islandLabelsPane.style.zIndex = '750'

      // MRK hatch pattern SVG
      if (!document.getElementById('mrkHatchDefs')) {
        const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        svgEl.setAttribute('id', 'mrkHatchDefs')
        svgEl.setAttribute('width', '0')
        svgEl.setAttribute('height', '0')
        svgEl.style.position = 'absolute'
        svgEl.innerHTML = `<defs><pattern id="mrkHatch" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#7c3aed" stroke-width="3" stroke-opacity="0.5" /></pattern></defs>`
        document.body.appendChild(svgEl)
      }

      // OSM tile layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom: 19,
        noWrap: true,
      }).addTo(map)

      // Build district index map for HSL hue
      const districtIndexMap = new Map<string, number>()
      features.forEach((f, idx) => districtIndexMap.set(f.id, idx))

      // --- Voronoi layer: current district highlighted, others as context ---
      const voronoiGroup = L.featureGroup()
      let currentBounds: ReturnType<typeof L.latLngBounds> | null = null

      voronoiFeatures.forEach((v) => {
        if (!v.geom_voronoi_geojson) return
        const isCurrent = v.id === currentDistrictId
        const distIdx = districtIndexMap.get(v.id) ?? features.findIndex((f) => f.id === v.id)
        const hue = getDistrictHue(distIdx >= 0 ? distIdx : 0)

        const layer = L.geoJSON(v.geom_voronoi_geojson as unknown as GeoJSON.GeoJsonObject, {
          style: isCurrent
            ? {
                color: `hsl(${hue}, 65%, 35%)`,
                weight: 4,
                fillColor: `hsl(${hue}, 65%, 60%)`,
                fillOpacity: 0.5,
              }
            : {
                color: `hsl(${hue}, 40%, 55%)`,
                weight: 1.5,
                fillColor: `hsl(${hue}, 40%, 75%)`,
                fillOpacity: 0.10,
              },
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          pane: 'districts' as any,
        })

        const feat = features.find((f) => f.id === v.id)
        const colorConfig = COMPOSITION_COLOR_MAP[feat?.composition_color ?? 'NONE'] ?? COMPOSITION_COLOR_MAP.NONE
        layer.bindTooltip(
          `<strong>${v.name}</strong>${isCurrent ? ' (aktuálny obvod)' : ''}<br/>${colorConfig.symbol} ${feat?.composition_color ?? 'NONE'}`,
          { sticky: true }
        )

        layer.addTo(voronoiGroup)

        if (isCurrent) {
          try {
            const b = layer.getBounds()
            if (b.isValid()) currentBounds = b
          } catch { /* ignore */ }
        }
      })

      voronoiGroup.addTo(map)

      // Fit to current district on load
      if (currentBounds) {
        map.fitBounds(currentBounds, { padding: [30, 30] })
      } else {
        map.setView(PSK_CENTER, PSK_DEFAULT_ZOOM)
      }

      // --- Island number labels ---
      const islandLabelsGroup = L.featureGroup()
      islands.forEach((island) => {
        if (!island.geom_geojson) return
        try {
          // Compute centroid via GeoJSON bounding approach
          const geom = island.geom_geojson as { type: string; coordinates: number[][][] | number[][] }
          let lon = 0
          let lat = 0
          let count = 0
          const coords: number[][] = geom.type === 'Polygon'
            ? (geom.coordinates as number[][][])[0]
            : []
          coords.forEach(([c0, c1]) => { lon += c0; lat += c1; count++ })
          if (count === 0) return
          lon /= count
          lat /= count

          const label = L.divIcon({
            html: `<div style="background:rgba(255,255,255,0.85);border:1.5px solid #374151;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#111827;line-height:1">${island.island_index + 1}</div>`,
            className: '',
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          })

          const streetsList = island.streets?.slice(0, 5).join(', ') || '—'
          const suffix = (island.streets?.length ?? 0) > 5 ? ` (+${(island.streets?.length ?? 0) - 5})` : ''
          L.marker([lat, lon], {
            icon: label,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            pane: 'islandLabels' as any,
            interactive: true,
          })
            .bindTooltip(
              `<strong>Ostrov ${island.island_index + 1}</strong><br/>${((island.area_m2 ?? 0) / 1_000_000).toFixed(3)} km²<br/>${island.street_count ?? 0} ulíc · ${island.house_count ?? 0} domov<br/>${streetsList}${suffix}`,
              { sticky: true }
            )
            .addTo(islandLabelsGroup)
        } catch { /* ignore malformed */ }
      })
      islandLabelsGroup.addTo(map)

      // --- School markers ---
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
          icon: makeSchoolIcon(feature.id === currentDistrictId ? 26 : 18),
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          pane: 'schools' as any,
        })
          .bindTooltip(`${feature.school_name ?? 'Škola'}${feature.id === currentDistrictId ? ' (aktuálna)' : ''}`)
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
        L.marker([lat, lon], {
          icon: makeSchoolIcon(16),
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          pane: 'schools' as any,
        })
          .bindTooltip(`${school.name}${school.kind ? ` (${school.kind})` : ''}`)
          .addTo(schoolsGroup)
      })

      schoolsGroup.addTo(map)

      // --- MRK overlays ---
      const mrkGroup = L.featureGroup()
      mrkOverlays.forEach((mrk) => {
        if (!mrk.geom_geojson) return
        const layer = L.geoJSON(mrk.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
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
        layer.bindTooltip(
          `<strong>MRK: ${mrk.name ?? 'Lokalita'}</strong>${mrk.severity_class ? `<br/>Kategória: ${mrk.severity_class}` : ''}`,
          { sticky: true }
        )
        layer.addTo(mrkGroup)
      })
      mrkGroup.addTo(map)

      // --- House points: current district larger markers ---
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

      // --- Street geocode points ---
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

      // Layer control
      L.control.layers(
        undefined,
        {
          'Voronoi obvody (všetky)': voronoiGroup,
          'Čísla ostrovov': islandLabelsGroup,
          'MRK lokality': mrkGroup,
          'Školy': schoolsGroup,
          'Domy z VZN (Google)': housePointsGroup,
          'Ulice (Street geocodes)': streetPointsGroup,
        },
        { collapsed: false }
      ).addTo(map)
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
      aria-label="Mapa školského obvodu s vrstvami"
      tabIndex={0}
    />
  )
}
