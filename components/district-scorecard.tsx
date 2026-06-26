import type { DistrictScorecardRow } from '@/lib/supabase/types'
import { VerdictRow } from './verdict-row'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'

interface DistrictScorecardProps {
  rows: DistrictScorecardRow[]
  // condition_code → AI-generated plain-Slovak explanation (precomputed,
  // optional; empty when explanations have not been generated yet).
  explanationByCode?: Record<string, string>
}

export function DistrictScorecard({ rows, explanationByCode = {} }: DistrictScorecardProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm" aria-label="Scorecard podmienok § 44">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              Podmienka
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              <Tooltip>
                <TooltipTrigger className="cursor-help underline decoration-dotted">
                  Hodnota
                </TooltipTrigger>
                <TooltipContent>Výsledok podmienky: PASS, FAIL, INCOMPLETE, RISK alebo INSUFFICIENT_DATA</TooltipContent>
              </Tooltip>
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              <Tooltip>
                <TooltipTrigger className="cursor-help underline decoration-dotted">
                  Dôvera
                </TooltipTrigger>
                <TooltipContent>Miera istoty výsledku — závisí od kvality vstupných dát (0 % = neoveriteľné, 100 % = plne potvrdené)</TooltipContent>
              </Tooltip>
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" scope="col">
              <Tooltip>
                <TooltipTrigger className="cursor-help underline decoration-dotted">
                  Úplnosť
                </TooltipTrigger>
                <TooltipContent>Koľko potrebných dát pre túto podmienku sa nám podarilo získať (100 % = máme všetko)</TooltipContent>
              </Tooltip>
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
            <VerdictRow
              key={row.condition_code}
              row={row}
              aiExplanation={explanationByCode[row.condition_code]}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
