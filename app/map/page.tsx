import { Suspense } from 'react'
import { RegionMap } from '@/components/region-map'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { createPublicClient } from '@/lib/supabase/server'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { DistrictMapFeature } from '@/lib/supabase/types'
import Link from 'next/link'
import { getColorSymbol, getColorLabel } from '@/lib/compliance/colors'

export const revalidate = 60

export const metadata = {
  title: 'Mapa PSK — Kontrola § 44',
}

async function fetchFeatures(): Promise<DistrictMapFeature[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('district_map_features').select('*')
    if (error) throw error
    return (data ?? []) as DistrictMapFeature[]
  } catch {
    return []
  }
}

export default async function MapPage() {
  const features = await fetchFeatures()
  const isEmpty = features.length === 0

  return (
    <div className="space-y-4">
      <DisclaimerBanner />

      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mapa PSK</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Školské obvody mesta Prešov — semaforová kompozícia podľa § 44
        </p>
      </div>

      {isEmpty && (
        <Alert>
          <AlertDescription>
            Engine ešte nebežal nad týmto územím. Mapa zobrazuje PSK hranicu bez dát.
          </AlertDescription>
        </Alert>
      )}

      {/* Map container */}
      <div
        className="rounded-lg border border-border overflow-hidden"
        style={{ height: '60vh', minHeight: 400 }}
        aria-describedby="map-fallback-table"
      >
        <Suspense fallback={<Skeleton className="w-full h-full rounded-none" />}>
          <RegionMap features={features} />
        </Suspense>
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
