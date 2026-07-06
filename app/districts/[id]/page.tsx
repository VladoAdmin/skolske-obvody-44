import { notFound } from 'next/navigation'
import Link from 'next/link'
import { createPublicClient } from '@/lib/supabase/server'
import { fetchAllRows } from '@/lib/supabase/fetch-all'
import { DistrictScorecard } from '@/components/district-scorecard'
import { DistrictFindings } from '@/components/district-findings'
import { DistrictDetailMap } from '@/components/district-detail-map'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import type {
  DistrictScorecardRow,
  DistrictMapFeature,
  SoSchoolMarker,
  SoHousePoint,
  SoDistrictAddressStats,
  SoDistrictStreetLine,
  SoFindingsPanelItem,
} from '@/lib/supabase/types'
import { CONDITION_LABELS_SK } from '@/lib/compliance/labels'
import { getColorClass, getColorSymbol, getColorLabel } from '@/lib/compliance/colors'
import { buildDistrictSummaries } from '@/lib/compliance/school-popup'
import { SHOW_COMPLIANCE } from '@/lib/compliance/step1'

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
    { data: rawSchools },
    { data: rawHousePoints },
    rawStreetLines,
    { data: rawAllScorecard },
    { data: rawFindings },
    { data: rawAddressStats },
    { data: rawDistrictFindings },
  ] = await Promise.all([
    sb.from('so_district_scorecard').select('*').eq('district_id', id),
    sb.from('so_district_map_features').select('*'),
    sb.from('so_school_markers').select('*'),
    sb.from('so_house_points').select('district_id,street,house_number,lat,lon,status,partial_match,formatted_address,point_geojson,valid,validation_reason'),
    // Streets pivot: the detail map uses the SAME street source as the main map.
    // Paged (>1000 rows, PostgREST cap) — see lib/supabase/fetch-all.ts.
    fetchAllRows<SoDistrictStreetLine>(
      sb,
      'so_district_street_linestrings',
      'district_id,school_id,street,is_fallback_point,linestring_geojson'
    ).catch(() => [] as SoDistrictStreetLine[]),
    sb.from('so_district_scorecard').select('district_id,condition_label_sk,condition_order,value,confidence,composition_color'),
    sb.from('so_findings_panel').select('district_id,status'),
    sb.from('so_district_address_stats').select('*').eq('district_id', id),
    sb
      .from('so_findings_panel')
      .select(
        'finding_id,district_id,condition_code,condition_label_sk,severity,severity_rank,status,evidence_public_text,provenance_source,is_demo'
      )
      .eq('district_id', id),
  ])

  if (scorecardError) throw scorecardError

  const rows = (rawRows ?? []) as DistrictScorecardRow[]
  const features = (allFeatures ?? []) as DistrictMapFeature[]
  const schools = (rawSchools ?? []) as SoSchoolMarker[]
  const housePoints = (rawHousePoints ?? []) as SoHousePoint[]
  const streetLines = rawStreetLines
  const addressStats = ((rawAddressStats ?? []) as SoDistrictAddressStats[])[0] ?? null
  const districtFindings = (rawDistrictFindings ?? []) as SoFindingsPanelItem[]

  // Per-district scorecard summaries + open-findings counts for school-pin popups.
  // Step 1: findings are wiped, so open-findings is empty.
  const allScorecard = (rawAllScorecard ?? []) as DistrictScorecardRow[]
  const findingsRows = (rawFindings ?? []) as { district_id: string; status: string }[]
  const openFindingsByDistrict: Record<string, number> = {}
  for (const f of findingsRows) {
    if (f.status === 'open') {
      openFindingsByDistrict[f.district_id] = (openFindingsByDistrict[f.district_id] ?? 0) + 1
    }
  }
  // No polygon islands in the streets pivot → no multi-part flag.
  const districtSummaries = buildDistrictSummaries(allScorecard, openFindingsByDistrict, {})

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

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">{header.district_name}</h1>
          {/* Step 1: NO compliance verdict badge — districts carry no compliance
              state until step 2. Gated by SHOW_COMPLIANCE. */}
          {SHOW_COMPLIANCE && (
            <span
              className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-bold ${colorClass}`}
              aria-label={colorLabel}
              title={colorLabel}
            >
              {colorSymbol} {colorLabel}
            </span>
          )}
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

      {/* Full-width detail map — SAME street rendering as the main map */}
      <DistrictDetailMap
        currentDistrictId={id}
        features={features}
        schools={schools}
        housePoints={housePoints}
        streetLines={streetLines}
        districtSummaries={districtSummaries}
      />

      {/* Step 1: NO § 44 compliance scorecard — all compliance analysis lives in
          step 2. The detail page shows the obvod's streets + the data-trust
          register stats only. Verdicts stay computed internally (engine SSOT).
          Gated by SHOW_COMPLIANCE. */}
      {!SHOW_COMPLIANCE ? (
        <section aria-labelledby="datatrust-heading">
          <h2 id="datatrust-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Dáta obvodu
          </h2>
          {addressStats && (
            <div className="mb-3 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">Autoritatívny register adries:</span>{' '}
                {addressStats.clean_habitable_addresses.toLocaleString('sk-SK')} obývateľných adries,{' '}
                {addressStats.clean_distinct_streets.toLocaleString('sk-SK')} ulíc{' '}
                (pokrytie ulíc z VZN {Math.round(addressStats.clean_street_coverage * 100)} %).{' '}
                Zdroj: vyčistený autoritatívny register adries a stavieb mesta Prešov.
              </p>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Mapa zobrazuje ulice tohto obvodu vo vlastnej farbe podľa školy.
            Vyhodnotenie podmienok § 44 bude doplnené v ďalšom kroku.
          </p>
        </section>
      ) : sorted.length > 0 ? (
        <section aria-labelledby="scorecard-heading">
          <h2 id="scorecard-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Scorecard podmienok § 44
          </h2>
          {addressStats && (
            <div className="mb-3 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">Autoritatívny register adries:</span>{' '}
                {addressStats.clean_habitable_addresses.toLocaleString('sk-SK')} obývateľných adries,{' '}
                {addressStats.clean_distinct_streets.toLocaleString('sk-SK')} ulíc{' '}
                (pokrytie ulíc z VZN {Math.round(addressStats.clean_street_coverage * 100)} %).{' '}
                Zdroj: vyčistený autoritatívny register adries a stavieb mesta Prešov. Slúži len ako
                podklad dôvery dát — nemení právny verdikt podmienok § 44.
              </p>
              {addressStats.mismatch_count > 0 && (
                <p className="mt-1.5">
                  <span
                    className="inline-flex items-center gap-1 cursor-help border-b border-dotted border-muted-foreground/60"
                    title={
                      'Adresy, ktorých reálna poloha (geokódovaná súradnica) padá mimo ' +
                      'obvodu, ktorý im prideľuje VZN — miesto na kontrolu, nie automatická ' +
                      'chyba. Ulice, ktoré VZN delí podľa rozsahu čísel medzi viac obvodov, ' +
                      'sa tu môžu objaviť legitímne. Nemení právny verdikt § 44.'
                    }
                  >
                    ⚠ Geometrický nesúlad:{' '}
                    <span className="font-medium text-foreground">
                      {addressStats.mismatch_count.toLocaleString('sk-SK')}
                    </span>{' '}
                    adries s reálnou polohou mimo prideleného obvodu
                  </span>
                </p>
              )}
            </div>
          )}
          <DistrictScorecard rows={sorted} />
        </section>
      ) : null}

      {SHOW_COMPLIANCE && districtFindings.length > 0 && (
        <DistrictFindings findings={districtFindings} />
      )}

      {SHOW_COMPLIANCE && sorted.length === 0 && (
        <Alert>
          <AlertTitle>Bez verdiktov</AlertTitle>
          <AlertDescription>
            Engine zatiaľ nehodnotil tento obvod. Overené pri poslednom engine behu.
          </AlertDescription>
        </Alert>
      )}

    </div>
  )
}
