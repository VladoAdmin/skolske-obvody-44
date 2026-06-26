import { Suspense } from 'react'
import { RegionMap } from '@/components/region-map'
import { FindingsPanel } from '@/components/findings-panel'
import { MapWithPanel } from '@/components/map/map-with-panel'
import { SummaryStrip } from '@/components/map/summary-strip'
import { createPublicClient } from '@/lib/supabase/server'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoDistrictIsland, SoPskMunicipality, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi, SoDistrictCleanGeom, SoHouseDot } from '@/lib/supabase/types'
import Link from 'next/link'
import { getColorSymbol, getColorLabel } from '@/lib/compliance/colors'

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
  const [features, schools, mrkOverlays, findings, overlaps, islands, municipalities, streetGeocodes, housePoints, voronoiGeom, cleanGeom, houseDots] = await Promise.all([
    fetchFeatures(),
    fetchSchools(),
    fetchMrkOverlays(),
    fetchFindings(),
    fetchOverlaps(),
    fetchIslands(),
    fetchMunicipalities(),
    fetchStreetGeocodes(),
    fetchHousePoints(),
    fetchVoronoiGeom(),
    fetchCleanGeom(),
    fetchHouseDots(),
  ])
  const isEmpty = features.length === 0
  const cleanShowcaseCount = cleanGeom.filter(
    (d) => d.geom_clean_metadata?.method === 'clean_polygon'
  ).length
  const cleanFallbackCount = cleanGeom.length - cleanShowcaseCount

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

      {/* Demo-data disclaimer — compact, collapsed by default (honest but not pushing content down) */}
      <details className="rounded-lg border border-amber-400 bg-amber-100 text-amber-950">
        <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold flex items-center gap-1.5 min-h-[44px] sm:min-h-0">
          <span aria-hidden="true">⚠</span>
          <span>Demo dáta — Register adries MŠSR nedostupný</span>
          <span className="ml-auto text-amber-800" aria-hidden="true">▾</span>
        </summary>
        <p className="px-3 pb-2 text-xs text-amber-900">
          Ukazujeme cieľový stav portálu nad rekonštruovanými polygónmi obvodov.
          Reálne dáta po sprístupnení Registra adries Ministerstva školstva.
          {cleanGeom.length > 0 && (
            <>
              {' '}
              <strong>{cleanShowcaseCount} obvody</strong> majú demo &bdquo;clean&ldquo; polygóny (hand-tuned),
              zvyšok ({cleanFallbackCount}) je Voronoi rekonštrukcia z VZN textu.
            </>
          )}
          {' '}
          <a
            href="/o-metodike#paragraf-44"
            className="font-semibold underline underline-offset-2 hover:text-amber-700"
          >
            Pozri metodiku →
          </a>
        </p>
      </details>

      {/* How to read the map — small expandable tip */}
      <details className="rounded-lg border border-blue-300 bg-blue-50 text-blue-900">
        <summary className="cursor-pointer list-none px-3 py-2 text-xs font-medium flex items-center gap-1.5 min-h-[44px] sm:min-h-0">
          <span>Ako čítať mapu</span>
          <span className="ml-auto text-blue-700" aria-hidden="true">▾</span>
        </summary>
        <p className="px-3 pb-2 text-xs text-blue-800">
          Mapa ukazuje {features.length} školských obvodov v Prešove farebne odlíšené.
          Sýto vyfarbené hranice = oblasť pridelená danej škole podľa VZN.
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
                findings={findings}
                overlaps={overlaps}
                islands={islands}
                municipalities={municipalities}
                streetGeocodes={streetGeocodes}
                housePoints={housePoints}
                voronoiGeom={voronoiGeom}
                cleanGeom={cleanGeom}
                houseDots={houseDots}
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
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3" style={{ background: 'repeating-linear-gradient(45deg, #7c3aed, #7c3aed 2px, transparent 2px, transparent 5px)' }}></span> MRK lokalita</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#2563eb' }}></span> Škola verejná (mesto Prešov)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#d97706' }}></span> Škola súkromná / cirkevná</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#dc2626', opacity: 0.25 }}></span> Prekryv obvodov: svetlejšie = 1, tmavšie = viac</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm border-2 border-dashed" style={{ borderColor: '#10b981', background: 'transparent' }}></span> Google hull (Sprint G)</span>
          <span className="mx-2">·</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{ background: '#10b981' }}></span> Adresné body (Google)</span>
        </p>
      </div>

      {/* A11y fallback table */}
      <section aria-labelledby="district-list-heading" id="map-fallback-table">
        <h2 id="district-list-heading" className="text-sm font-semibold mb-2">
          Zoznam obvodov
        </h2>
        {isEmpty ? (
          <p className="text-xs text-muted-foreground">Žiadne obvody — engine ešte nezhodnotil.</p>
        ) : (
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-xs" aria-label="Zoznam obvodov s semaforom">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground" scope="col">Obvod</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground" scope="col">Semafor</th>
                </tr>
              </thead>
              <tbody>
                {features.map((f) => (
                  <tr key={f.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                    <td className="p-0">
                      <Link
                        href={`/districts/${f.id}`}
                        className="flex items-center min-h-[44px] px-3 py-2 text-primary hover:text-primary/80"
                      >
                        {f.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <span aria-label={getColorLabel(f.composition_color)}>
                        {getColorSymbol(f.composition_color)} {getColorLabel(f.composition_color)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
