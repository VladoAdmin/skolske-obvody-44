import { Suspense } from 'react'
import { RegionMap } from '@/components/region-map'
import { FindingsPanel } from '@/components/findings-panel'
import { DistrictTogglePanel } from '@/components/district-toggle-panel'
import { MapWithPanel } from '@/components/map/map-with-panel'
import { SummaryStrip } from '@/components/map/summary-strip'
import { createPublicClient } from '@/lib/supabase/server'
import { fetchAllRows } from '@/lib/supabase/fetch-all'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoMrkLocality, SoFindingsPanelItem, SoPskMunicipality, SoHousePoint, SoHouseDot, DistrictScorecardRow, SoDistrictStreetLine, SoStreetCoverageGap } from '@/lib/supabase/types'
import Link from 'next/link'
import { getColorSymbol, getColorLabel, getRowTint, getRowText } from '@/lib/compliance/colors'
import { buildDistrictSummaries } from '@/lib/compliance/school-popup'
import { SHOW_COMPLIANCE } from '@/lib/compliance/step1'
import { getDistrictHue } from '@/lib/config/region'

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

// STREETS PIVOT: districts render as their VZN-assigned streets, coloured per
// school. One row per drawn segment (LineString, or a Point for fallback streets
// with no OSM line). Single SSOT used by the main map and the detail page.
// The view has ~3000 rows — above the PostgREST 1000-row cap — so it must be
// paged via fetchAllRows or whole neighbourhoods go missing from the map.
async function fetchStreetLines(): Promise<SoDistrictStreetLine[]> {
  try {
    const sb = createPublicClient()
    return await fetchAllRows<SoDistrictStreetLine>(
      sb,
      'so_district_street_linestrings',
      'district_id,school_id,street,is_fallback_point,linestring_geojson'
    )
  } catch {
    return []
  }
}

// VLA-14: engine-classified coverage gaps (vzn_gap / data_gap). The GUI only
// renders what the engine wrote — no client-side classification.
async function fetchCoverageGaps(): Promise<SoStreetCoverageGap[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb
      .from('so_street_coverage_gaps')
      .select('street,category,in_register,in_vzn,register_address_count,has_osm_line,reason_sk,is_demo,geom_geojson')
    if (error) throw error
    return (data ?? []) as SoStreetCoverageGap[]
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
      .select('district_id,street,house_number,lat,lon,status,partial_match,formatted_address,point_geojson,valid,validation_reason,is_demo')
    if (error) throw error
    return (data ?? []) as SoHousePoint[]
  } catch {
    return []
  }
}

export default async function MapPage() {
  const [features, schools, mrkOverlays, mrkLocalities, findings, municipalities, streetLines, housePoints, houseDots, scorecardRows, coverageGaps] = await Promise.all([
    fetchFeatures(),
    fetchSchools(),
    fetchMrkOverlays(),
    fetchMrkLocalities(),
    fetchFindings(),
    fetchMunicipalities(),
    fetchStreetLines(),
    fetchHousePoints(),
    fetchHouseDots(),
    fetchScorecard(),
    fetchCoverageGaps(),
  ])
  const isEmpty = features.length === 0

  // Open-findings count per district (status = open) for the school-pin popup.
  // Step 1: findings are wiped, so this is empty — kept so the popup builder
  // signature is unchanged when findings return in step 2.
  const openFindingsByDistrict: Record<string, number> = {}
  for (const f of findings) {
    if (f.status === 'open') {
      openFindingsByDistrict[f.district_id] = (openFindingsByDistrict[f.district_id] ?? 0) + 1
    }
  }
  // No polygon islands in the streets pivot → no multi-part flag.
  const districtSummaries = buildDistrictSummaries(scorecardRows, openFindingsByDistrict, {})

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mapa Slovenska — Školské obvody § 44</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Prešovský samosprávny kraj — pilot mesta Prešov
        </p>
      </div>

      {/* High-level pilot summary — first thing visible, above the fold on mobile */}
      <SummaryStrip features={features} findings={findings} coverageGaps={coverageGaps} />

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
          Mapa ukazuje {features.length} školských obvodov v Prešove. Každý obvod je vykreslený
          ako sústava jeho ulíc (podľa VZN) vo vlastnej farbe. Kliknutím na školu sa jej ulice
          zvýraznia a ostatné obvody sa stlmia. Ulica, ktorá patrí viacerým obvodom (hraničná),
          sa kreslí vo farbe každého z nich — nie je to chyba.
          Pre kompletný overview kliknite na konkrétny obvod v zozname dole.
        </p>
        <p className="px-3 pb-2 text-xs text-blue-800">
          Ulice bez farby obvodu sú explicitne klasifikované:{' '}
          <span className="font-medium text-red-700">VZN medzera</span> (červená prerušovaná) — ulica
          je v Registri adries mesta, ale žiadne VZN ju nepriraďuje k obvodu (štrukturálny nález § 44);{' '}
          <span className="font-medium text-gray-600">Nedostatočné dáta</span> (sivá prerušovaná) —
          názov z mapových podkladov sa nedá priradiť k registru, stav je „neurčené — dátová medzera“
          a nejde o porušenie. Kliknutím na úsek sa zobrazí vysvetlenie s dôkazmi.
        </p>
        <p className="px-3 pb-2 text-xs text-blue-800">
          Značky škôl sú farebne rozlíšené podľa zriaďovateľa:{' '}
          <span className="inline-flex items-center gap-1 align-middle"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#2563eb' }}></span> modrá = verejná (mesto Prešov)</span>,{' '}
          <span className="inline-flex items-center gap-1 align-middle"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#d97706' }}></span> oranžová = súkromná / cirkevná</span>.
        </p>
      </details>

      {/* Map + district-list panel layout — responsive via MapWithPanel.
          VLA-20: the side panel holds ONLY the district list; findings moved
          to their own section below the map. */}
      <div aria-describedby="map-fallback-table">
        <MapWithPanel
          districtsCount={features.length}
          mapSlot={
            <Suspense fallback={<Skeleton className="w-full h-full rounded-none" />}>
              <RegionMap
                features={features}
                schools={schools}
                mrkOverlays={mrkOverlays}
                mrkLocalities={mrkLocalities}
                municipalities={municipalities}
                streetLines={streetLines}
                housePoints={housePoints}
                houseDots={houseDots}
                coverageGaps={coverageGaps}
                findings={findings}
                districtSummaries={districtSummaries}
                initialMode="psk"
              />
            </Suspense>
          }
          panelSlot={
            <div className="h-full bg-background overflow-y-auto">
              <DistrictTogglePanel features={features} />
            </div>
          }
        />
      </div>

      {/* Findings — own full-width panel below the map (VLA-20: moved out of
          the district panel; stays on this page so click → fly-to keeps
          working, and is visible together with the district list). */}
      <section
        aria-label="Nálezy"
        className="mt-4 rounded-lg border border-border overflow-hidden"
      >
        <div className="h-[45vh] min-h-[280px]">
          <FindingsPanel findings={findings} features={features} />
        </div>
      </section>

      {/* Map legend */}
      <div className="hidden md:block">
        <p className="text-xs text-muted-foreground mt-2">
          Legenda: <span className="inline-flex items-center gap-1"><span className="inline-block w-6 h-1 rounded-sm" style={{ background: 'hsl(210,70%,45%)' }}></span> Ulice obvodu (farba podľa školy)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-6 h-0 border-t-2 border-dashed" style={{ borderColor: '#dc2626' }}></span> VZN medzera — ulica bez obvodu (nález § 44)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-6 h-0 border-t-2 border-dashed" style={{ borderColor: '#6b7280' }}></span> Nedostatočné dáta — neurčené (nie je porušenie)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#7c3aed' }}></span> MRK lokalita — bod (Atlas MRK, budova/lokalita)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#2563eb' }}></span> Škola verejná (mesto Prešov)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#d97706' }}></span> Škola súkromná / cirkevná</span>
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
            Žiadne obvody.
          </p>
        ) : (
          <ul
            className="list-none m-0 p-0 border-t border-gov-border"
            aria-label={SHOW_COMPLIANCE ? 'Zoznam obvodov so semaforom' : 'Zoznam obvodov'}
          >
            {features.map((f, index) => (
              <li
                key={f.id}
                className={`border-b border-gov-border last:border-b-0 border-l-4 ${
                  SHOW_COMPLIANCE ? getRowTint(f.composition_color) : 'border-l-transparent'
                }`}
              >
                <Link
                  href={`/districts/${f.id}`}
                  className="flex items-center gap-3 min-h-[44px] px-4 py-3 hover:bg-gov-blue50 transition-colors"
                >
                  {SHOW_COMPLIANCE ? (
                    <span
                      className={`inline-flex shrink-0 items-center gap-1 font-semibold text-sm ${getRowText(
                        f.composition_color
                      )}`}
                      aria-label={getColorLabel(f.composition_color)}
                    >
                      <span aria-hidden="true">{getColorSymbol(f.composition_color)}</span>
                      {getColorLabel(f.composition_color)}
                    </span>
                  ) : (
                    // Step 1: identify the obvod ONLY by its per-school street
                    // colour — no compliance state.
                    <span
                      className="inline-block shrink-0 w-3.5 h-3.5 rounded-full border border-black/10"
                      style={{ background: `hsl(${getDistrictHue(index)}, 65%, 45%)` }}
                      aria-hidden="true"
                    />
                  )}
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
