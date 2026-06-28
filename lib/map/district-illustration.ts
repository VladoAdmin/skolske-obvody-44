// Shared § 44 map-illustration builder.
//
// Renders the geometric illustrations that correspond to a district's ENGINE
// findings (overlap strip / island / long-distance Pa line / P-e MRK exclusion /
// P-f overcrowding ring). Lifted verbatim from region-map.client.tsx so the
// PSK overview map and the per-district detail map draw identical evidence from
// the same code — no duplicated illustration logic.
//
// All geometry is derived from data already on the client; nothing here changes
// an engine verdict. The builder returns the Leaflet feature group plus an
// optional DOM legend node so the caller manages add/remove + cleanup itself.

import type {
  DistrictMapFeature,
  SoFindingsPanelItem,
  SoDistrictOverlap,
  SoDistrictIsland,
  SoHousePoint,
  SoMrkOverlay,
} from '@/lib/supabase/types'

// Pull "712 / 560" style numbers out of a Pf evidence string (žiakov X > kapacita Y).
function parsePfNumbers(text: string | null | undefined): { students: number; capacity: number } | null {
  if (!text) return null
  const m = text.match(/(\d{2,5})\s*>\s*kapacita\s*(\d{2,5})/i)
  if (!m) return null
  const students = Number(m[1])
  const capacity = Number(m[2])
  if (!Number.isFinite(students) || !Number.isFinite(capacity) || capacity <= 0) return null
  return { students, capacity }
}

// Ray-casting point-in-polygon against a GeoJSON (Multi)Polygon's OUTER rings.
function pointInGeom(
  pt: [number, number], // [lon, lat]
  geom: Record<string, unknown> | null | undefined
): boolean {
  if (!geom) return false
  const type = geom.type as string | undefined
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const coords = geom.coordinates as any
  if (!coords) return false
  const polys: number[][][][] =
    type === 'MultiPolygon' ? coords : type === 'Polygon' ? [coords] : []
  const [x, y] = pt
  for (const poly of polys) {
    const ring = poly[0]
    if (!ring) continue
    let inside = false
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0]
      const yi = ring[i][1]
      const xj = ring[j][0]
      const yj = ring[j][1]
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
        inside = !inside
      }
    }
    if (inside) return true
  }
  return false
}

// Collect outer-ring vertices of a GeoJSON (Multi)Polygon as [lon, lat] pairs.
function outerRingVertices(
  geom: Record<string, unknown> | null | undefined
): [number, number][] {
  if (!geom) return []
  const type = geom.type as string | undefined
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const coords = geom.coordinates as any
  if (!coords) return []
  const polys: number[][][][] =
    type === 'MultiPolygon' ? coords : type === 'Polygon' ? [coords] : []
  const out: [number, number][] = []
  for (const poly of polys) {
    const ring = poly[0]
    if (!ring) continue
    for (const pt of ring) out.push([pt[0], pt[1]])
  }
  return out
}

// Haversine straight-line distance in metres between two [lat, lon] points.
function haversineMeters(a: [number, number], b: [number, number]): number {
  const R = 6371000
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b[0] - a[0])
  const dLon = toRad(b[1] - a[1])
  const lat1 = toRad(a[0])
  const lat2 = toRad(b[0])
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

// Farthest REAL geocoded address (housePoints) of a district from its school.
function farthestHousePointFromSchool(
  points: { district_id: string; lat: number | null; lon: number | null; street: string | null; house_number: string | null; valid?: boolean | null }[],
  districtId: string,
  school: [number, number] // [lat, lon]
): { point: [number, number]; meters: number; label: string } | null {
  let best: { point: [number, number]; meters: number; label: string } | null = null
  for (const p of points) {
    if (p.district_id !== districtId) continue
    if (p.valid === false) continue
    if (p.lat == null || p.lon == null) continue
    const d = haversineMeters(school, [p.lat, p.lon])
    if (!best || d > best.meters) {
      const label = `${(p.street ?? '').trim()} ${(p.house_number ?? '').trim()}`.trim()
      best = { point: [p.lat, p.lon], meters: d, label }
    }
  }
  return best
}

export interface BuildDistrictIllustrationArgs {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  L: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  map: any
  feature: DistrictMapFeature
  findings: SoFindingsPanelItem[]
  islands: SoDistrictIsland[]
  overlaps: SoDistrictOverlap[]
  housePoints: SoHousePoint[]
  mrkOverlays: SoMrkOverlay[]
  // Leaflet pane to draw the illustration into (must already exist on the map).
  pane: string
  // The map container element to mount the legend box into.
  container: HTMLElement | null
}

export interface DistrictIllustration {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  group: any
  legend: HTMLDivElement | null
}

// Build the DEMO § 44 finding illustration group + legend for ONE district.
//
// Honest scope (item 8b): every shape this draws is a DEMO/illustrative layer —
// the seeded overlap, the seeded island, the Pa long-distance line, the Pe MRK
// exclusion and the Pf overcrowding ring. It NEVER alters an engine verdict and
// only fires for districts carrying the corresponding demo finding. Returns null
// when the district has no drawable demo finding (caller draws nothing). The
// caller owns adding `group`/`legend` to the map and removing them on cleanup.
export function buildDemoFindingIllustration({
  L,
  map,
  feature,
  findings,
  islands,
  overlaps,
  housePoints,
  mrkOverlays,
  pane,
  container,
}: BuildDistrictIllustrationArgs): DistrictIllustration | null {
  // Findings the engine produced for THIS district (drives which illustrations
  // to draw — keeps the map in sync with the engine).
  const myFindings = findings.filter((f) => f.district_id === feature.id)
  const hasFinding = (code: string) => myFindings.some((f) => f.condition_code === code)
  const findingOf = (code: string) => myFindings.find((f) => f.condition_code === code)

  const group = L.featureGroup()
  const legendRows: string[] = []

  // (1) ISLAND / strip — detached fragment that belongs elsewhere.
  islands
    .filter(
      (isl) =>
        isl.is_demo === true &&
        isl.district_id === feature.id &&
        isl.geom_geojson
    )
    .forEach((isl) => {
      L.geoJSON(isl.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
        style: {
          color: '#b91c1c', // red-700 outline
          weight: 3,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          fillColor: 'url(#mrkHatch)' as any, // hatched → reads as anomaly
          fillOpacity: 1,
          dashArray: '6,4',
        },
        pane,
      })
        .bindTooltip(
          '<strong>ostrov (S2)</strong><br/>Odčlenená lišta v obvode patrí inému obvodu.',
          { sticky: true }
        )
        .addTo(group)
    })
  if (
    islands.some(
      (isl) => isl.is_demo === true && isl.district_id === feature.id && isl.geom_geojson
    )
  ) {
    legendRows.push(
      '<span style="display:inline-block;width:12px;height:12px;border:2px dashed #b91c1c;background:repeating-linear-gradient(45deg,#7c3aed,#7c3aed 2px,transparent 2px,transparent 5px);margin-right:6px;vertical-align:-2px"></span>ostrov (S2)'
    )
  }

  // (2) OVERLAP — same street segment claimed by two districts.
  const myOverlaps = overlaps.filter(
    (ov) =>
      ov.is_demo === true &&
      ov.overlap_geojson &&
      (ov.district_a_id === feature.id || ov.district_b_id === feature.id)
  )
  myOverlaps.forEach((ov) => {
    const other =
      ov.district_a_id === feature.id ? ov.district_b_name : ov.district_a_name
    L.geoJSON(ov.overlap_geojson as unknown as GeoJSON.GeoJsonObject, {
      style: {
        fillColor: '#facc15', // amber-400 high-visibility
        fillOpacity: 0.6,
        color: '#b45309', // amber-700 border
        weight: 3,
        dashArray: '6,4',
      },
      pane,
    })
      .bindTooltip(
        `<strong>prekryv ulice (S2)</strong><br/>Zdieľané s obvodom ${other}.`,
        { sticky: true }
      )
      .addTo(group)
  })
  if (myOverlaps.length > 0) {
    legendRows.push(
      '<span style="display:inline-block;width:12px;height:12px;border:2px dashed #b45309;background:#facc15;margin-right:6px;vertical-align:-2px"></span>prekryv ulice (S2)'
    )
  }

  // (3) LONG DISTANCE (Pa) — dashed line from the assigned school to the REAL
  // geocoded address (housePoints) that is farthest from it. Drawn ONLY when
  // the engine produced a Pa finding and the real air-line exceeds 2 km.
  const schoolGeom = feature.school_geom_geojson as
    | { type: string; coordinates: [number, number] }
    | null
  if (hasFinding('Pa') && schoolGeom && schoolGeom.type === 'Point') {
    const [slon, slat] = schoolGeom.coordinates
    const school: [number, number] = [slat, slon]
    const far = farthestHousePointFromSchool(housePoints, feature.id, school)
    if (far && far.meters > 2000) {
      const km = (far.meters / 1000).toFixed(1)
      const addr = far.label || 'adresa'
      L.polyline([school, far.point], {
        color: '#dc2626', // red-600
        weight: 3,
        dashArray: '8,5',
        opacity: 0.9,
        pane,
      })
        .bindTooltip(
          `<strong>~${km} km (Pa)</strong><br/>Najvzdialenejšia adresa „${addr}“ od školy (vzdušná čiara, reálny geokód).`,
          { sticky: true }
        )
        .addTo(group)
      // Highlight the critical address itself.
      L.circleMarker(far.point, {
        radius: 6,
        fillColor: '#dc2626',
        color: '#7f1d1d',
        weight: 2,
        fillOpacity: 0.95,
        pane,
      })
        .bindTooltip(`<strong>${addr}</strong><br/>~${km} km od školy`, { sticky: true })
        .addTo(group)
      L.marker(far.point, {
        icon: L.divIcon({
          html: `<div style="background:#dc2626;color:#fff;font-size:11px;font-weight:700;padding:1px 5px;border-radius:4px;white-space:nowrap;box-shadow:0 1px 2px rgba(0,0,0,.4);transform:translateY(-16px)">${addr} · ~${km} km (Pa)</div>`,
          className: 'demo-distance-label',
          iconSize: [0, 0],
          iconAnchor: [0, 0],
        }),
        pane,
      }).addTo(group)
      legendRows.push(
        `<span style="display:inline-block;width:14px;height:0;border-top:3px dashed #dc2626;margin-right:6px;vertical-align:3px"></span>~${km} km — adresa „${addr}“ (Pa)`
      )
    }
  }

  // (4) P-e SEGREGÁCIA (Atlas MRK) — exclusion of the marginalised Roma
  // community locality by the obvod boundary. Drawn only when the engine
  // produced a Pe signal; overlays the REAL MRK locality polygon and classifies
  // its outer-ring vertices: those the obvod boundary leaves OUTSIDE the obvod
  // are the "vyčlenená / segregačná" signal.
  if (hasFinding('Pe')) {
    let drewMrk = false
    mrkOverlays.forEach((mrk) => {
      if (!mrk.geom_geojson) return
      const verts = outerRingVertices(mrk.geom_geojson)
      if (verts.length === 0) return
      const outside = verts.filter(
        (v) => !pointInGeom(v, feature.geom_geojson)
      )
      const inside = verts.length - outside.length
      if (inside === 0 || outside.length === 0) return

      // (4a) MRK locality area — strong purple outline.
      L.geoJSON(mrk.geom_geojson as unknown as GeoJSON.GeoJsonObject, {
        style: {
          color: '#6d28d9', // violet-700 outline
          weight: 2.5,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          fillColor: 'url(#mrkHatch)' as any,
          fillOpacity: 1,
          dashArray: '4,3',
        },
        pane,
      })
        .bindTooltip(
          `<strong>MRK lokalita (Atlas MRK)</strong><br/>Hranica obvodu ju rozdeľuje — časť ostáva mimo obvodu ${feature.name}.`,
          { sticky: true }
        )
        .addTo(group)

      // (4b) The EXCLUDED MRK vertices — small violet dots just OUTSIDE the
      // obvod boundary. Thin the set for legibility.
      const step = Math.max(1, Math.round(outside.length / 40))
      outside.forEach((v, i) => {
        if (i % step !== 0) return
        L.circleMarker([v[1], v[0]], {
          radius: 3,
          fillColor: '#7c3aed',
          color: '#4c1d95',
          weight: 1,
          fillOpacity: 0.9,
          pane,
        }).addTo(group)
      })

      // (4c) Annotation marker at the excluded-cluster centroid.
      const ox = outside.reduce((a, v) => a + v[0], 0) / outside.length
      const oy = outside.reduce((a, v) => a + v[1], 0) / outside.length
      L.marker([oy, ox], {
        icon: L.divIcon({
          html:
            '<div style="background:#6d28d9;color:#fff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:5px;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.45);max-width:180px">vyčlenená MRK lokalita<br/><span style="font-weight:500;font-size:10px">segregačný signál (P-e)</span></div>',
          className: 'demo-mrk-exclusion-label',
          iconSize: [0, 0],
          iconAnchor: [0, 0],
        }),
        pane,
      }).addTo(group)
      drewMrk = true
    })
    if (drewMrk) {
      legendRows.push(
        '<span style="display:inline-block;width:12px;height:12px;border:2px dashed #6d28d9;background:repeating-linear-gradient(45deg,#7c3aed,#7c3aed 2px,transparent 2px,transparent 5px);margin-right:6px;vertical-align:-2px"></span>vyčlenená MRK lokalita (P-e signál)'
      )
    }
  }

  // (5) P-f DEMOGRAFIA / KAPACITA — overcrowding. Colour the obvod school pin +
  // drop a "preplnené" badge showing N žiakov / M kapacita. Drawn only when the
  // engine produced a Pf SIGNAL finding; numbers read from its evidence text.
  const pfFinding = findingOf('Pf')
  const oc = pfFinding ? parsePfNumbers(pfFinding.evidence_public_text) : null
  const schoolGeomPf = feature.school_geom_geojson as
    | { type: string; coordinates: [number, number] }
    | null
  if (oc && schoolGeomPf && schoolGeomPf.type === 'Point') {
    const [plon, plat] = schoolGeomPf.coordinates
    const pct = Math.round((oc.students / oc.capacity) * 100)
    L.circleMarker([plat, plon], {
      radius: 16,
      fillColor: '#dc2626',
      fillOpacity: 0.18,
      color: '#b91c1c',
      weight: 2.5,
      dashArray: '5,4',
      pane,
    })
      .bindTooltip(
        `<strong>Preplnené (P-f, demo)</strong><br/>Počet žiakov ${oc.students} prekračuje kapacitu ${oc.capacity} (≈ ${pct} %).<br/>Odhad — podklad pre plánovanie, nie nález o porušení.`,
        { sticky: true }
      )
      .addTo(group)
    L.marker([plat, plon], {
      icon: L.divIcon({
        html: `<div style="background:#dc2626;color:#fff;font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;white-space:nowrap;box-shadow:0 1px 2px rgba(0,0,0,.4);transform:translateY(-22px)">${oc.students}/${oc.capacity} žiakov (preplnené)</div>`,
        className: 'demo-overcrowd-label',
        iconSize: [0, 0],
        iconAnchor: [0, 0],
      }),
      pane,
    }).addTo(group)
    legendRows.push(
      `<span style="display:inline-block;width:12px;height:12px;border:2px dashed #b91c1c;border-radius:50%;background:rgba(220,38,38,.18);margin-right:6px;vertical-align:-2px"></span>preplnené ${oc.students}/${oc.capacity} (P-f signál)`
    )
  }

  if (legendRows.length === 0) return null

  // Legend box (bottom-left, above attribution) summarising the findings drawn.
  let legend: HTMLDivElement | null = null
  if (container) {
    legend = document.createElement('div')
    legend.className = 'demo-finding-legend'
    legend.style.cssText =
      'position:absolute;left:8px;bottom:24px;z-index:1000;background:rgba(255,255,255,.95);border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;font-size:11px;line-height:1.7;box-shadow:0 1px 4px rgba(0,0,0,.2);max-width:230px;pointer-events:none'
    const hasSignal = legendRows.some((r) => r.includes('P-e') || r.includes('P-f'))
    const signalNote = hasSignal
      ? '<div style="margin-top:6px;padding-top:5px;border-top:1px solid #e5e7eb;font-weight:500;color:#6b7280;font-size:10px;line-height:1.5">P-e a P-f sú <strong>signály (upozornenia)</strong>, nie verdikt — § 44 ich priamo nehodnotí.</div>'
      : ''
    legend.innerHTML =
      `<div style="font-weight:700;margin-bottom:4px">Nálezy § 44 (demo)</div>${legendRows.join('<br/>')}${signalNote}`
    container.appendChild(legend)
  }

  // Caller adds group to map; mark void use of map to keep signature aligned
  // with the region-map closure (which also references map for fitBounds).
  void map

  return { group, legend }
}
