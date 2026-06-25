import Link from 'next/link'
import { createPublicClient } from '@/lib/supabase/server'
import type { MunicipalitySummary } from '@/lib/supabase/types'

export const revalidate = 60
export const metadata = { title: 'Zriaďovatelia — Kontrola § 44' }

async function fetchSummaries(): Promise<MunicipalitySummary[]> {
  try {
    const sb = createPublicClient()
    const { data, error } = await sb.from('municipalities_summary').select('*')
    if (error) throw error
    return (data ?? []) as MunicipalitySummary[]
  } catch {
    return []
  }
}

export default async function MunicipalitiesPage() {
  const summaries = await fetchSummaries()

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Zriaďovatelia</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Súhrnný scorecard per obec / zriaďovateľ. Pilot: Prešov.
        </p>
      </div>

      {summaries.length === 0 ? (
        <div className="rounded-lg border border-border p-8 text-center text-sm text-muted-foreground">
          Žiadne dáta — engine ešte nezhodnotil.
        </div>
      ) : (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-sm" aria-label="Zriaďovatelia">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">Obec</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground" scope="col">Obvody</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground" scope="col">Školy</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground text-red-700" scope="col">🔴</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground text-orange-700" scope="col">🟠</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground text-green-700" scope="col">🟢</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground" scope="col">Nálezy</th>
              </tr>
            </thead>
            <tbody>
              {summaries.map((s) => (
                <tr key={s.municipality_id} className="border-b border-border last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-2">
                    <Link href={`/municipalities/${s.municipality_id}`} className="text-primary underline hover:text-primary/80">
                      {s.name}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.districts_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.schools_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.red_districts_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.orange_districts_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.green_districts_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.open_findings_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
