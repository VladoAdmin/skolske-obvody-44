import { notFound } from 'next/navigation'
import Link from 'next/link'
import { createPublicClient } from '@/lib/supabase/server'
import { fetchAllRows } from '@/lib/supabase/fetch-all'
import type { DistrictMapFeature, MunicipalitySummary, SoDistrictStreetLine } from '@/lib/supabase/types'
import { RegionMap } from '@/components/region-map'
import { getColorSymbol, getColorLabel } from '@/lib/compliance/colors'
import { SHOW_COMPLIANCE } from '@/lib/compliance/step1'

export const revalidate = 60

interface Props {
  params: { id: string }
}

export default async function MunicipalityDetailPage({ params }: Props) {
  const { id } = params
  const sb = createPublicClient()

  const [summaryRes, featuresRes, streetLines] = await Promise.all([
    sb.from('so_municipalities_summary').select('*').eq('municipality_id', id).maybeSingle(),
    sb.from('so_district_map_features').select('*'),
    // Paged (>1000 rows, PostgREST cap) — see lib/supabase/fetch-all.ts.
    fetchAllRows<SoDistrictStreetLine>(
      sb,
      'so_district_street_linestrings',
      'district_id,school_id,street,is_fallback_point,linestring_geojson,segment_id',
      'segment_id'
    ).catch(() => [] as SoDistrictStreetLine[]),
  ])

  const summary = summaryRes.data as MunicipalitySummary | null
  // If no summary, municipality is not Prešov or doesn't exist
  if (!summary) notFound()

  const features = (featuresRes.data ?? []) as DistrictMapFeature[]

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{summary.name}</h1>
        <p className="text-sm text-muted-foreground">
          {summary.districts_count} obvodov · {summary.schools_count} škôl
          {SHOW_COMPLIANCE && <> · {summary.open_findings_count} otvorených nálezov</>}
        </p>
      </div>

      {/* Mini stat row — step 1: no RED/ORANGE/GREEN compliance breakdown. */}
      {SHOW_COMPLIANCE && (
        <div className="flex gap-4 text-xs">
          <span className="text-red-700">✕ {summary.red_districts_count} RED</span>
          <span className="text-orange-700">~ {summary.orange_districts_count} ORANGE</span>
          <span className="text-green-700">✓ {summary.green_districts_count} GREEN</span>
          <span className="text-gray-500">? {summary.none_districts_count} NONE</span>
        </div>
      )}

      {/* Mini map */}
      <div className="rounded-lg border border-border overflow-hidden" style={{ height: 300 }}>
        <RegionMap features={features} schools={[]} mrkOverlays={[]} streetLines={streetLines} initialMode="psk" />
      </div>

      {/* Districts list */}
      <section aria-labelledby="districts-heading">
        <h2 id="districts-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
          Obvody
        </h2>
        {features.length === 0 ? (
          <p className="text-sm text-muted-foreground">Žiadne obvody.</p>
        ) : (
          <ul className="space-y-1">
            {features.map((f) => (
              <li key={f.id} className="flex items-center gap-2 text-sm">
                {SHOW_COMPLIANCE && (
                  <span
                    className="font-mono text-xs w-4 text-center"
                    aria-label={getColorLabel(f.composition_color)}
                  >
                    {getColorSymbol(f.composition_color)}
                  </span>
                )}
                <Link href={`/districts/${f.id}`} className="text-primary underline hover:text-primary/80">
                  {f.name}
                </Link>
                {f.school_name && (
                  <span className="text-xs text-muted-foreground">({f.school_name})</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
