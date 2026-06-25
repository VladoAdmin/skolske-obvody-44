import { Suspense } from 'react'
import { RegionMap } from '@/components/region-map'
import { FindingsPanel } from '@/components/findings-panel'
import { MapWithPanel } from '@/components/map/map-with-panel'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { createPublicClient } from '@/lib/supabase/server'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap } from '@/lib/supabase/types'
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

export default async function MapPage() {
  const [features, schools, mrkOverlays, findings, overlaps] = await Promise.all([
    fetchFeatures(),
    fetchSchools(),
    fetchMrkOverlays(),
    fetchFindings(),
    fetchOverlaps(),
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
                initialMode="sk"
              />
            </Suspense>
          }
          panelSlot={<FindingsPanel findings={findings} />}
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
          <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 border-2 border-red-700 border-dashed"></span> Prekryv obvodov</span>
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
