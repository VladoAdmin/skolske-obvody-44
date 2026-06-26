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
} from '@/lib/supabase/types'
import { CONDITION_LABELS_SK } from '@/lib/compliance/labels'
import { getColorClass, getColorSymbol, getColorLabel } from '@/lib/compliance/colors'

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
  ] = await Promise.all([
    sb.from('so_district_scorecard').select('*').eq('district_id', id),
    sb.from('so_district_map_features').select('*'),
    sb.from('so_district_voronoi').select('id,name,geom_voronoi_geojson,geom_voronoi_metadata'),
    sb.from('so_school_markers').select('*'),
    sb.from('so_mrk_overlays').select('*'),
    sb.from('so_house_points').select('district_id,street,house_number,lat,lon,status,partial_match,formatted_address,point_geojson,valid,validation_reason'),
    sb.from('so_street_geocodes').select('district_id,street,lat,lon,status,partial_match,formatted_address,point_geojson'),
    sb.from('so_district_islands').select('*').eq('district_id', id).order('island_index'),
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

  const multiIslandCount = islands.length
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
      />

      {/* Scorecard or empty state */}
      {sorted.length > 0 ? (
        <section aria-labelledby="scorecard-heading">
          <h2 id="scorecard-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Scorecard podmienok § 44
          </h2>
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

      {/* Island geometry section */}
      {multiIslandCount > 0 && (
        <section aria-labelledby="islands-heading" className="space-y-3">
          <h2 id="islands-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Geometria a ostrovy obvodu
          </h2>

          {multiIslandCount > 1 && (
            <Alert className="border-amber-300 bg-amber-50 text-amber-900">
              <AlertTitle className="text-amber-800">
                {multiIslandCount} disconnected ostrov{multiIslandCount > 4 ? 'ov' : multiIslandCount > 1 ? 'y' : ''}
              </AlertTitle>
              <AlertDescription className="text-amber-800 text-xs">
                Engine vytvoril <strong>{multiIslandCount}</strong> disconnected ostrovov pre tento obvod.
                Toto je dôsledok VZN, ktorý priraďuje ZŠ aj vzdialené ulice.
                Možné dôvody: školský obvod historicky vznikol z viacerých škôl, alebo škola má
                špecializáciu pre konkrétne adresy.{' '}
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
