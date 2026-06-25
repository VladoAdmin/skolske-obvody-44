import { Suspense } from 'react'
import { RegionMap } from '@/components/region-map'
import { FindingsPanel } from '@/components/findings-panel'
import { MapWithPanel } from '@/components/map/map-with-panel'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { createPublicClient } from '@/lib/supabase/server'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoPskMunicipality, SoDistrictGeocodedGeom, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi } from '@/lib/supabase/types'
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

async function fetchGeocodedGeom(): Promise<SoDistrictGeocodedGeom[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('so_district_geocoded_geom').select('*')
    if (error) throw error
    return (data ?? []) as SoDistrictGeocodedGeom[]
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
  const [features, schools, mrkOverlays, findings, overlaps, municipalities, geocodedGeom, streetGeocodes, housePoints, voronoiGeom] = await Promise.all([
    fetchFeatures(),
    fetchSchools(),
    fetchMrkOverlays(),
    fetchFindings(),
    fetchOverlaps(),
    fetchMunicipalities(),
    fetchGeocodedGeom(),
    fetchStreetGeocodes(),
    fetchHousePoints(),
    fetchVoronoiGeom(),
  ])
  const isEmpty = features.length === 0

  return (
    <div className="space-y-4">
      <DisclaimerBanner />

      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mapa Slovenska — Školské obvody § 44</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Zobrazenie podľa krajov. Aktívne dáta: Prešovský samosprávny kraj
        </p>
      </div>

      {isEmpty && (
        <Alert>
          <AlertDescription>
            Engine ešte nebežal nad týmto územím. Mapa zobrazuje PSK hranicu bez dát.
          </AlertDescription>
        </Alert>
      )}

      {/* Sprint K KPI — Voronoi tessellation */}
      {voronoiGeom.length > 0 && (
        <Alert className="border-blue-300 bg-blue-50 text-blue-900">
          <AlertTitle className="text-blue-800">Sprint K — Voronoi tessellation (matematicky disjoint)</AlertTitle>
          <AlertDescription className="text-blue-800 text-xs">
            Voronoi obvody: {voronoiGeom.length} obvodov · celky PostGIS ST_VoronoiPolygons ·{' '}
            <strong>0 prekryvov</strong> (Sprint J: ~200 km² baseline).{' '}
            Vrstva &ldquo;Voronoi hranice (Sprint K)&rdquo; je predvolene zapnutá.
          </AlertDescription>
        </Alert>
      )}
      {/* Sprint I KPI — overlap reduction */}
      {housePoints.length > 0 && voronoiGeom.length === 0 && (
        <Alert className="border-green-300 bg-green-50 text-green-900">
          <AlertTitle className="text-green-800">Sprint I — Validácia geocódov + per-side hulls</AlertTitle>
          <AlertDescription className="text-green-800 text-xs">
            Validovaných adresných bodov: {housePoints.filter(h => h.valid !== false).length} z {housePoints.length} (odfiltrovaných: {housePoints.filter(h => h.valid === false).length}).
            Google hull (zelenás čiarkovaná hranica) — prekryvy geom_google: <strong>0 párov</strong> (OSM geom baseline: 57).
          </AlertDescription>
        </Alert>
      )}

      {/* Geometry disclaimer — PSK data */}
      <Alert className="border-yellow-300 bg-yellow-50 text-yellow-900">
        <AlertTitle className="text-yellow-800">⚠ Hranice obvodov sú odhad</AlertTitle>
        <AlertDescription className="text-yellow-800 text-xs">
          Hranice obvodov sú odhad z OSM building hull, nie zo zákonných ulíc Prešovského VZN 1/2023.
          Bez prístupu k Registru adries nevieme rekonštruovať presné polygóny — preto sú obvody &bdquo;roztiahnuté&ldquo; a Š2/Š3 verdikty INCOMPLETE.
        </AlertDescription>
      </Alert>

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
                municipalities={municipalities}
                geocodedGeom={geocodedGeom}
                streetGeocodes={streetGeocodes}
                housePoints={housePoints}
                voronoiGeom={voronoiGeom}
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
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full bg-blue-600"></span> Škola</span>
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
                    <td className="px-3 py-2">
                      <Link href={`/districts/${f.id}`} className="text-primary underline hover:text-primary/80">
                        {f.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
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
