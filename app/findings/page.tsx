import { Suspense } from 'react'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { FindingsTable } from '@/components/findings-table'
import { FindingsFilters } from '@/components/findings-filters'
import { createPublicClient } from '@/lib/supabase/server'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { FindingPublic } from '@/lib/supabase/types'

export const revalidate = 60

export const metadata = {
  title: 'Register nálezov — Kontrola § 44',
}

const PAGE_SIZE = 50

interface Props {
  searchParams: {
    severity?: string
    status?: string
    condition?: string
    page?: string
  }
}

async function fetchFindings(searchParams: Props['searchParams']) {
  try {
    const sb = createPublicClient()
    const page = Math.max(1, parseInt(searchParams.page ?? '1', 10))
    const from = (page - 1) * PAGE_SIZE
    const to = from + PAGE_SIZE - 1

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let query: any = sb
      .from('findings_public')
      .select('*', { count: 'exact' })
      .order('severity_rank', { ascending: false })
      .order('created_at', { ascending: false })
      .range(from, to)

    if (searchParams.severity) {
      query = query.eq('severity', searchParams.severity)
    }
    if (searchParams.status) {
      query = query.eq('status', searchParams.status)
    }
    if (searchParams.condition) {
      query = query.eq('condition_code', searchParams.condition)
    }

    const { data, count, error } = await query
    if (error) throw error
    return { findings: (data ?? []) as FindingPublic[], totalCount: count ?? 0, page, error: false as const }
  } catch (err) {
    console.error('fetchFindings error:', err)
    return { findings: [], totalCount: 0, page: 1, error: true as const }
  }
}

export default async function FindingsPage({ searchParams }: Props) {
  const { findings, totalCount, page, error } = await fetchFindings(searchParams)
  const hasFilters = !!(searchParams.severity || searchParams.status || searchParams.condition)

  return (
    <div className="space-y-4">
      <DisclaimerBanner />

      <div>
        <h1 className="text-xl font-semibold tracking-tight">Register nálezov</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Odchýlky a riziká identifikované enginom pre obvody mesta Prešov
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Chyba načítania</AlertTitle>
          <AlertDescription>
            Nepodarilo sa načítať nálezy. Skúste obnoviť stránku alebo nahláste správcovi.
          </AlertDescription>
        </Alert>
      ) : (
        <>
          <Suspense fallback={null}>
            <FindingsFilters />
          </Suspense>

          {findings.length === 0 && !hasFilters ? (
            <div className="rounded-lg border border-border p-8 text-center text-sm text-muted-foreground">
              Engine zatiaľ nevygeneroval žiadny nález.
            </div>
          ) : (
            <FindingsTable
              findings={findings}
              totalCount={totalCount}
              page={page}
              pageSize={PAGE_SIZE}
            />
          )}
        </>
      )}
    </div>
  )
}
