import { Suspense } from 'react'
import { RegionMap } from '@/components/region-map'
import { FindingsPanel } from '@/components/findings-panel'
import { MapWithPanel } from '@/components/map/map-with-panel'
import { SummaryStrip } from '@/components/map/summary-strip'
import { createPublicClient } from '@/lib/supabase/server'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoMrkLocality, SoFindingsPanelItem, SoDistrictOverlap, SoDistrictIsland, SoPskMunicipality, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi, SoDistrictCleanGeom, SoHouseDot, DistrictScorecardRow } from '@/lib/supabase/types'
import Link from 'next/link'
import { getColorSymbol, getColorLabel, getRowTint, getRowText } from '@/lib/compliance/colors'
import { buildDistrictSummaries, buildMultiPartByDistrict } from '@/lib/compliance/school-popup'

export const revalidate = 60

export const metadata = {
  title: 'Mapa Slovenska — Školské obvody § 44',
}

async function fetchFeatures(): Promise<DistrictMapFeature[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_district_map_features').select('*')
    if (error) throw error
    return (data ?? []) as DistrictMapFeature[]
  } catch {
    return []
  }
}

async function fetchSchools(): Promise<SoSchoolMarker[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_school_markers').select('*')
    if (error) throw error
    return (data ?? []) as SoSchoolMarker[]
  } catch {
    return []
  }
}

async function fetchMrkOverlays(): Promise<SoMrkOverlay[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_mrk_overlays').select('*')
    if (error) throw error
    return (data ?? []) as SoMrkOverlay[]
  } catch {
    return []
  }
}

async function fetchMrkLocalities(): Promise<SoMrkLocality[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_mrk_localities').select('*')
    if (error) throw error
    return (data ?? []) as SoMrkLocality[]
  } catch {
    return []
  }
}

async function fetchFindings(): Promise<SoFindingsPanelItem[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb
      .from('so_findings_panel')
      .select('*')
      .order('severity_rank', { ascending: true })
    if (error) throw error
    return (data ?? []) as SoFindingsPanelItem[]
  } catch {
    return []
  }
}

async function fetchOverlaps(): Promise<SoDistrictOverlap[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_district_overlaps').select('*')
    if (error) throw error
    return (data ?? []) as SoDistrictOverlap[]
  } catch {
    return []
  }
}

async function fetchIslands(): Promise<SoDistrictIsland[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_district_islands').select('*')
    if (error) throw error
    return (data ?? []) as SoDistrictIsland[]
  } catch {
    return []
  }
}

async function fetchMunicipalities(): Promise<SoPskMunicipality[]> {
  try {
    const sb = createPublicClient()
    // Fetch without geom to keep payload small — geom only for map rendering
    const { data, error } = await sb
      .from('so_psk_municipalities')
      .select('id,name,slug,geom_geojson,schools_count,districts_count')
    if (error) throw error
    return (data ?? []) as SoPskMunicipality[]
  } catch {
    return []
  }
}

async function fetchStreetGeocodes(): Promise<SoStreetGeocode[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb
      .from('so_street_geocodes')
      .select('district_id,street,lat,lon,status,partial_match,formatted_address,point_geojson')
    if (error) throw error
    return (data ?? []) as SoStreetGeocode[]
  } catch {
    return []
  }
}

async function fetchVoronoiGeom(): Promise<SoDistrictVoronoi[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_district_voronoi').select('id,name,geom_voronoi_geojson,geom_voronoi_metadata')
    if (error) throw error
    return (data ?? []) as SoDistrictVoronoi[]
  } catch {
    return []
  }
}

async function fetchCleanGeom(): Promise<SoDistrictCleanGeom[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb
      .from('so_district_clean_geom')
      .select('id,name,school_id,geom_clean_geojson,geom_clean_metadata')
    if (error) throw error
    return (data ?? []) as SoDistrictCleanGeom[]
  } catch {
    return []
  }
}

async function fetchHouseDots(): Promise<SoHouseDot[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb
      .from('so_house_dots')
      .select('district_id,street,house_number,lat,lon')
    if (error) throw error
    return (data ?? []) as SoHouseDot[]
  } catch {
    return []
  }
}

async function fetchScorecard(): Promise<DistrictScorecardRow[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb
      .from('so_district_scorecard')
      .select('district_id,condition_label_sk,condition_order,value,confidence,composition_color')
    if (error) throw error
    return (data ?? []) as DistrictScorecardRow[]
  } catch {
    return []
  }
}

async function fetchHousePoints(): Promise<SoHousePoint[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb
      .from('so_house_points')
      .select('district_id,street,house_number,lat,lon,status,partial_match,formatted_address,point_geojson,valid,validation_reason')
    if (error) throw error
    return (data ?? []) as SoHousePoint[]
  } catch {
    return []
  }
}

export default async function MapPage() {
  const [features, schools, mrkOverlays, mrkLocalities, findings, overlaps, islands, municipalities, streetGeocodes, housePoints, voronoiGeom, cleanGeom, houseDots, scorecardRows] = await Promise.all([
    fetchFeatures(),
    fetchSchools(),
    fetchMrkOverlays(),
    fetchMrkLocalities(),
    fetchFindings(),
    fetchOverlaps(),
    fetchIslands(),
    fetchMunicipalities(),
    fetchStreetGeocodes(),
    fetchHousePoints(),
    fetchVoronoiGeom(),
    fetchCleanGeom(),
    fetchHouseDots(),
    fetchScorecard(),
  ])
  const isEmpty = features.length === 0

  // Open-findings count per district (status = open) for the school-pin popup.
  const openFindingsByDistrict: Record<string, number> = {}
  for (const f of findings) {
    if (f.status === 'open') {
      openFindingsByDistrict[f.district_id] = (openFindingsByDistrict[f.district_id] ?? 0) + 1
    }
  }
  const multiPartByDistrict = buildMultiPartByDistrict(islands)
  const districtSummaries = buildDistrictSummaries(scorecardRows, openFindingsByDistrict, multiPartByDistrict)

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mapa Slovenska — Školské obvody § 44</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Prešovský samosprávny kraj — pilot mesta Prešov
        </p>
      </div>

      {/* High-level pilot summary — first thing visible, above the fold on mobile */}
      <SummaryStrip features={features} findings={findings} />

      {isEmpty && (
        <Alert>
          <AlertDescription>
            Engine ešte nebežal nad týmto územím. Mapa zobrazuje PSK hranicu bez dát.
          </AlertDescription>
        </Alert>
      )}

      {/* How to read the map — small expandable tip */}
      <details className="rounded-lg border border-blue-300 bg-blue-50 text-blue-900">
        <summary className="cursor-pointer list-none px-3 py-2 text-xs font-medium flex items-center gap-1.5 min-h-[44px] sm:min-h-0">
          <span>Ako čítať mapu</span>
          <span className="ml-auto text-blue-700" aria-hidden="true">▾</span>
        </summary>
        <p className="px-3 pb-2 text-xs text-blue-800">
          Mapa ukazuje {features.length} školských obvodov v Prešove, každý má vlastnú farbu hranice.
          Hranice sú zvýraznené tenkou bielou linkou, aby ste jasne videli, kde jeden obvod
          končí a druhý začína; po prejdení myšou (alebo ťuknutí) sa daný obvod vyfarbí.
          Šrafované oblasti = prekryvy (chyba VZN — 2 obvody nárokujú tú istú adresu).
          Pre kompletný overview kliknite na konkrétny obvod v zozname dole.
        </p>
        <p className="px-3 pb-2 text-xs text-blue-800">
          Značky škôl sú farebne rozlíšené podľa zriaďovateľa:{' '}
          <span className="inline-flex items-center gap-1 align-middle"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#2563eb' }}></span> modrá = verejná (mesto Prešov)</span>,{' '}
          <span className="inline-flex items-center gap-1 align-middle"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#d97706' }}></span> oranžová = súkromná / cirkevná</span>.
        </p>
      </details>

      {/* Map + findings panel layout — responsive via MapWithPanel */}
      <div aria-describedby="map-fallback-table">
        <MapWithPanel
          findingsCount={findings.length}
          mapSlot={
            <Suspense fallback={<Skeleton className="w-full h-full rounded-none" />}>
              <RegionMap
                features={features}
                schools={schools}
                mrkOverlays={mrkOverlays}
                mrkLocalities={mrkLocalities}
                findings={findings}
                overlaps={overlaps}
                islands={islands}
                municipalities={municipalities}
                streetGeocodes={streetGeocodes}
                housePoints={housePoints}
                voronoiGeom={voronoiGeom}
                cleanGeom={cleanGeom}
                houseDots={houseDots}
                districtSummaries={districtSummaries}
                initialMode="sk"
              />
            </Suspense>
          }
          panelSlot={<FindingsPanel findings={findings} features={features} />}
        />
      </div>

      {/* Map legend */}
      <div className="hidden md:block">
        <p className="text-xs text-muted-foreground mt-2">
          Legenda: <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: 'hsl(40,65%,60%)', opacity: 0.5 }}></span> Obvod (kategorická farba)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#7c3aed' }}></span> MRK lokalita — bod (Atlas MRK, budova/lokalita)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#2563eb' }}></span> Škola verejná (mesto Prešov)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#d97706' }}></span> Škola súkromná / cirkevná</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#dc2626', opacity: 0.25 }}></span> Prekryv obvodov: svetlejšie = 1, tmavšie = viac</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{ background: '#10b981' }}></span> Adresné body obvodov (Google geokód, priblížte sa)</span>
        </p>
      </div>

      {/* Obvody results list — gov-style semafor rows (item 11). Each row carries
          a soft tint + a strong left bar + a strong-coloured TEXTUAL verdict, so
          the legend's traffic light actually appears on the rows. The textual
          verdict (V súlade / Čiastočne / Nesúlad) is always present — colour is
          an addition, never colour-only (a11y + colour-blind safety). */}
      <section
        aria-labelledby="district-list-heading"
        id="map-fallback-table"
        className="rounded shadow-gov bg-white overflow-hidden"
      >
        <h2
          id="district-list-heading"
          className="text-section font-semibold uppercase text-gov-blue px-4 pt-4 pb-2"
        >
          Zoznam obvodov
        </h2>
        {isEmpty ? (
          <p className="text-xs text-muted-foreground px-4 pb-4">
            Žiadne obvody — engine ešte nezhodnotil.
          </p>
        ) : (
          <ul
            className="list-none m-0 p-0 border-t border-gov-border"
            aria-label="Zoznam obvodov so semaforom"
          >
            {features.map((f) => (
              <li
                key={f.id}
                className={`border-b border-gov-border last:border-b-0 border-l-4 ${getRowTint(
                  f.composition_color
                )}`}
              >
                <Link
                  href={`/districts/${f.id}`}
                  className="flex items-center gap-3 min-h-[44px] px-4 py-3 hover:bg-gov-blue50 transition-colors"
                >
                  <span
                    className={`inline-flex shrink-0 items-center gap-1 font-semibold text-sm ${getRowText(
                      f.composition_color
                    )}`}
                    aria-label={getColorLabel(f.composition_color)}
                  >
                    <span aria-hidden="true">{getColorSymbol(f.composition_color)}</span>
                    {getColorLabel(f.composition_color)}
                  </span>
                  <span className="text-gov-blue text-sm truncate">{f.name}</span>
                  <span className="ml-auto text-gov-muted" aria-hidden="true">
                    ›
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
