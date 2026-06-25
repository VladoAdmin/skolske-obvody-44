import { notFound } from 'next/navigation'
import Link from 'next/link'
import { createPublicClient } from '@/lib/supabase/server'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { DistrictScorecard } from '@/components/district-scorecard'
import { DistrictMiniMap } from '@/components/district-mini-map'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import type { DistrictScorecardRow, DistrictMapFeature } from '@/lib/supabase/types'
import { CONDITION_LABELS_SK } from '@/lib/compliance/labels'
import { getColorClass, getColorSymbol, getColorLabel } from '@/lib/compliance/colors'

export const revalidate = 60

interface Props {
  params: { id: string }
}

export default async function DistrictPage({ params }: Props) {
  const { id } = params
  const sb = createPublicClient()

  // Fetch scorecard rows
  const { data: rawRows, error: scorecardError } = await sb
    .from('so_district_scorecard')
    .select('*')
    .eq('district_id', id)

  if (scorecardError) {
    throw scorecardError
  }

  const rows = (rawRows ?? []) as DistrictScorecardRow[]

  // Header info: from rows or fallback to district_map_features
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
    // No scorecard rows: check if district even exists
    const { data: mf } = await sb
      .from('so_district_map_features')
      .select('*')
      .eq('id', id)
      .maybeSingle()

    if (!mf) {
      notFound()
    }

    const mfTyped = mf as DistrictMapFeature
    header = {
      district_name: mfTyped.name,
      municipality_id: mfTyped.municipality_id,
      municipality_name: null,
      vzn_ref_url: null,
      composition_color: mfTyped.composition_color,
    }
    mapFeature = mfTyped
  }

  // Fetch map feature for mini map (if not already fetched)
  if (!mapFeature) {
    const { data: mf } = await sb
      .from('so_district_map_features')
      .select('*')
      .eq('id', id)
      .maybeSingle()
    mapFeature = mf as DistrictMapFeature | null
  }

  // Sort by condition_order (from view or TS fallback)
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

      {/* Mini map — full-width on mobile, constrained on desktop */}
      <div className="w-full lg:max-w-2xl">
        <DistrictMiniMap feature={mapFeature} />
      </div>

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
    </div>
  )
}
