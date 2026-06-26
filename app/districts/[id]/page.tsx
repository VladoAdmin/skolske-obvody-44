import { notFound } from 'next/navigation'
import Link from 'next/link'
import { createPublicClient } from '@/lib/supabase/server'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { DistrictScorecard } from '@/components/district-scorecard'
import { DistrictDetailMap } from '@/components/district-detail-map'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import type {
  DistrictScorecardRow,
  DistrictMapFeature,
  SoSchoolMarker,
  SoMrkOverlay,
  SoHousePoint,
  SoStreetGeocode,
  SoDistrictVoronoi,
  SoDistrictIsland,
  SoDistrictAddressStats,
} from '@/lib/supabase/types'
import { CONDITION_LABELS_SK } from '@/lib/compliance/labels'
import { getColorClass, getColorSymbol, getColorLabel } from '@/lib/compliance/colors'
import { buildDistrictSummaries, buildMultiPartByDistrict } from '@/lib/compliance/school-popup'

export const revalidate = 60

interface Props {
  params: { id: string }
}

export default async function DistrictPage({ params }: Props) {
  const { id } = params
  const sb = createPublicClient()

  // Fetch all data in parallel
  const [
    { data: rawRows, error: scorecardError },
    { data: allFeatures },
    { data: rawVoronoi },
    { data: rawSchools },
    { data: rawMrk },
    { data: rawHousePoints },
    { data: rawStreetGeocodes },
    { data: rawIslands },
    { data: rawAllScorecard },
    { data: rawFindings },
    { data: rawAddressStats },
  ] = await Promise.all([
    sb.from('so_district_scorecard').select('*').eq('district_id', id),
    sb.from('so_district_map_features').select('*'),
    sb.from('so_district_voronoi').select('id,name,geom_voronoi_geojson,geom_voronoi_metadata'),
    sb.from('so_school_markers').select('*'),
    sb.from('so_mrk_overlays').select('*'),
    sb.from('so_house_points').select('district_id,street,house_number,lat,lon,status,partial_match,formatted_address,point_geojson,valid,validation_reason'),
    sb.from('so_street_geocodes').select('district_id,street,lat,lon,status,partial_match,formatted_address,point_geojson'),
    sb.from('so_district_islands').select('*').eq('district_id', id).order('island_index'),
    sb.from('so_district_scorecard').select('district_id,condition_label_sk,condition_order,value,confidence,composition_color'),
    sb.from('so_findings_panel').select('district_id,status'),
    sb.from('so_district_address_stats').select('*').eq('district_id', id),
  ])

  if (scorecardError) throw scorecardError

  const rows = (rawRows ?? []) as DistrictScorecardRow[]
  const features = (allFeatures ?? []) as DistrictMapFeature[]
  const voronoiFeatures = (rawVoronoi ?? []) as SoDistrictVoronoi[]
  const schools = (rawSchools ?? []) as SoSchoolMarker[]
  const mrkOverlays = (rawMrk ?? []) as SoMrkOverlay[]
  const housePoints = (rawHousePoints ?? []) as SoHousePoint[]
  const streetGeocodes = (rawStreetGeocodes ?? []) as SoStreetGeocode[]
  const islands = (rawIslands ?? []) as SoDistrictIsland[]
  const addressStats = ((rawAddressStats ?? []) as SoDistrictAddressStats[])[0] ?? null

  // Per-district scorecard summaries + open-findings counts for school-pin popups.
  const allScorecard = (rawAllScorecard ?? []) as DistrictScorecardRow[]
  const findingsRows = (rawFindings ?? []) as { district_id: string; status: string }[]
  const openFindingsByDistrict: Record<string, number> = {}
  for (const f of findingsRows) {
    if (f.status === 'open') {
      openFindingsByDistrict[f.district_id] = (openFindingsByDistrict[f.district_id] ?? 0) + 1
    }
  }
  // Only the current district's islands are fetched here, so the popup
  // multi-part flag is accurate for this obvod's own school pin.
  const multiPartByDistrict = buildMultiPartByDistrict(islands)
  const districtSummaries = buildDistrictSummaries(allScorecard, openFindingsByDistrict, multiPartByDistrict)

  // Header info
  let header: {
    district_name: string
    municipality_id: string | null
    municipality_name: string | null
    vzn_ref_url: string | null
    composition_color: string | null
  }

  let mapFeature: DistrictMapFeature | null = null

  if (rows.length > 0) {
    header = {
      district_name: rows[0].district_name,
      municipality_id: rows[0].municipality_id,
      municipality_name: rows[0].municipality_name,
      vzn_ref_url: rows[0].vzn_ref_url,
      composition_color: rows[0].composition_color ?? null,
    }
  } else {
    const mf = features.find((f) => f.id === id) ?? null
    if (!mf) {
      notFound()
    }
    header = {
      district_name: mf.name,
      municipality_id: mf.municipality_id,
      municipality_name: null,
      vzn_ref_url: null,
      composition_color: mf.composition_color,
    }
    mapFeature = mf
  }

  if (!mapFeature) {
    mapFeature = features.find((f) => f.id === id) ?? null
  }

  const sorted = [...rows].sort((a, b) => {
    const aOrder = a.condition_order ?? CONDITION_LABELS_SK[a.condition_code]?.order ?? 99
    const bOrder = b.condition_order ?? CONDITION_LABELS_SK[b.condition_code]?.order ?? 99
    return aOrder - bOrder
  })

  const colorSymbol = getColorSymbol(header.composition_color)
  const colorLabel = getColorLabel(header.composition_color)
  const colorClass = getColorClass(header.composition_color)

  // Multi-part review flag: a school obvod should be a single contiguous
  // polygon. After sliver cleanup, the parts that remain are substantial real
  // splits that need human review. We derive parts straight from the (cleaned)
  // island rows: real (non-demo) parts ordered by area, largest first.
  const realParts = islands
    .filter((i) => i.is_demo !== true)
    .map((i) => (i.area_m2 ?? 0) / 1_000_000)
    .sort((a, b) => b - a)
  const partsCount = realParts.length
  const isMultiPart = partsCount > 1
  const biggestKm2 = realParts[0] ?? 0
  const otherPartsKm2 = realParts.slice(1)

  const checkedUrl = 'zsmeralova.edupage.org, zsmeralova.sk, presov.sk'

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Disclaimer always shown on district page */}
      <DisclaimerBanner alwaysShow />

      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">{header.district_name}</h1>
          <span
            className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-bold ${colorClass}`}
            aria-label={colorLabel}
            title={colorLabel}
          >
            {colorSymbol} {colorLabel}
          </span>
        </div>

        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          {header.municipality_id && (
            <Link href={`/municipalities/${header.municipality_id}`} className="underline hover:text-foreground">
              {header.municipality_name ?? 'Obec'}
            </Link>
          )}
          {header.vzn_ref_url && (
            <a
              href={header.vzn_ref_url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="underline hover:text-foreground"
            >
              VZN (odkaz)
            </a>
          )}
        </div>
      </div>

      {/* Full-width detail map */}
      <DistrictDetailMap
        currentDistrictId={id}
        features={features}
        voronoiFeatures={voronoiFeatures}
        schools={schools}
        mrkOverlays={mrkOverlays}
        housePoints={housePoints}
        streetGeocodes={streetGeocodes}
        islands={islands}
        districtSummaries={districtSummaries}
      />

      {/* Scorecard or empty state */}
      {sorted.length > 0 ? (
        <section aria-labelledby="scorecard-heading">
          <h2 id="scorecard-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Scorecard podmienok § 44
          </h2>
          {addressStats && (
            <p className="mb-3 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Autoritatívny register adries:</span>{' '}
              {addressStats.habitable_addresses.toLocaleString('sk-SK')} obývateľných adries,{' '}
              {addressStats.register_streets.toLocaleString('sk-SK')} ulíc{' '}
              (pokrytie ulíc z VZN {Math.round(addressStats.street_coverage * 100)} %).{' '}
              Zdroj: register adries MV SR. Slúži len ako podklad dôvery dát — nemení
              právny verdikt podmienok § 44.
            </p>
          )}
          <DistrictScorecard rows={sorted} />
        </section>
      ) : (
        <Alert>
          <AlertTitle>Bez verdiktov</AlertTitle>
          <AlertDescription>
            Engine zatiaľ nehodnotil tento obvod. Overené pri poslednom engine behu.
          </AlertDescription>
        </Alert>
      )}

      {/* Island geometry section — only when the obvod is genuinely multi-part
          (or carries a demo anomaly seed). Single-polygon obvody have one
          main-body island row and should not show a spurious "ostrovy" block. */}
      {(isMultiPart || islands.some((i) => i.is_demo === true)) && (
        <section aria-labelledby="islands-heading" className="space-y-3">
          <h2 id="islands-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Geometria a ostrovy obvodu
          </h2>

          {isMultiPart && (
            <Alert className="border-amber-300 bg-amber-50 text-amber-900">
              <AlertTitle className="text-amber-800">
                ⚠ Tento obvod má {partsCount} oddelených častí — na kontrolu
              </AlertTitle>
              <AlertDescription className="text-amber-800 text-xs">
                Školský obvod by mal byť <strong>jedna súvislá plocha</strong>.
                Tento sa skladá z <strong>{partsCount}</strong> oddelených častí
                (najväčšia <strong>{biggestKm2.toFixed(2)} km²</strong>
                {otherPartsKm2.length > 0 && (
                  <>, ostatné: {otherPartsKm2.map((a) => `${a.toFixed(2)} km²`).join(', ')}</>
                )}
                ). Drobné artefakty geometrie už boli zlúčené do susedných obvodov;
                tieto väčšie časti sú ponechané a označené na{' '}
                <strong>manuálnu kontrolu</strong> (história zlúčených škôl,
                špecializované adresy, alebo chyba vo VZN).{' '}
                <strong>Aktuálne sa nepodarilo overiť žiaden školský dôvod</strong>{' '}
                (overené na {checkedUrl}).
              </AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            {islands.map((island) => {
              const areaKm2 = ((island.area_m2 ?? 0) / 1_000_000).toFixed(3)
              const streetCount = island.street_count ?? 0
              const houseCount = island.house_count ?? 0
              const streets = island.streets ?? []

              return (
                <details
                  key={island.island_index}
                  className="rounded border border-border bg-muted/20"
                >
                  <summary className="flex items-center gap-3 px-4 py-2.5 cursor-pointer select-none hover:bg-muted/40 transition-colors">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-slate-200 text-slate-800 text-xs font-bold shrink-0">
                      {island.island_index + 1}
                    </span>
                    <span className="text-sm font-medium">
                      Ostrov {island.island_index + 1}
                    </span>
                    <span className="text-xs text-muted-foreground ml-auto">
                      {areaKm2} km² · {streetCount} ulíc · {houseCount} domov
                    </span>
                  </summary>

                  <div className="px-4 pb-3 pt-1 text-xs text-muted-foreground">
                    {streets.length > 0 ? (
                      <ul className="mt-1 space-y-0.5">
                        {streets.map((street) => (
                          <li key={street} className="text-foreground">{street}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="italic">Žiadne priradiné ulice z geocódovaných adresných bodov.</p>
                    )}
                  </div>
                </details>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}
