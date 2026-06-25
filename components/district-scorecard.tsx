import type { DistrictScorecardRow } from '@/lib/supabase/types'
import { VerdictRow } from './verdict-row'

interface DistrictScorecardProps {
  rows: DistrictScorecardRow[]
}

export function DistrictScorecard({ rows }: DistrictScorecardProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm" aria-label="Scorecard podmienok § 44">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Podmienka
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Hodnota
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Dôvera
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Úplnosť
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Semafor
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Príznaky
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Dôkaz
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <VerdictRow key={row.condition_code} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
