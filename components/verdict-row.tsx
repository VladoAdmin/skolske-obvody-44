import type { DistrictScorecardRow } from '@/lib/supabase/types'
import { getColorClass, getColorSymbol } from '@/lib/compliance/colors'
import { getConditionDescription } from '@/lib/compliance/labels'
import { ProvenanceLink } from './provenance-link'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'

interface VerdictRowProps {
  row: DistrictScorecardRow
  // Precomputed AI-generated plain-Slovak explanation for this condition.
  // Optional — absent until the explanations have been generated.
  aiExplanation?: string
}

function AiExplanation({ text }: { text: string }) {
  return (
    <div className="mt-2 rounded border border-violet-200 bg-violet-50 px-2 py-1.5">
      <p className="flex items-center gap-1 text-[11px] font-semibold text-violet-800">
        <span aria-hidden>✦</span> Vysvetlenie (generované AI)
      </p>
      <p className="mt-0.5 text-xs leading-relaxed text-violet-900">{text}</p>
      <p className="mt-1 text-[10px] italic text-violet-700">
        Generované umelou inteligenciou ako pomôcka pre čitateľa — nemení právny
        verdikt podmienky.
      </p>
    </div>
  )
}

const VALUE_DESCRIPTIONS: Record<string, string> = {
  PASS:              'Podmienka splnená — všetky dostupné dáta sú v poriadku.',
  FAIL:              'Podmienka nesplnená — zákonná požiadavka nie je dodržaná.',
  INCOMPLETE:        'Chýbajú vstupné dáta — výsledok zatiaľ nevieme určiť.',
  RISK:              'Rizikový signál — indikátor poukazuje na potenciálny problém.',
  INSUFFICIENT_DATA: 'Príliš málo dát — výsledok nemá dostatočnú výpovednú hodnotu.',
}

function ValueBadge({ value }: { value: string }) {
  const classMap: Record<string, string> = {
    PASS:              'bg-green-100 text-green-800 border-green-300',
    FAIL:              'bg-red-100 text-red-800 border-red-300',
    INCOMPLETE:        'bg-yellow-100 text-yellow-800 border-yellow-300',
    RISK:              'bg-orange-100 text-orange-800 border-orange-300',
    INSUFFICIENT_DATA: 'bg-blue-100 text-blue-800 border-blue-300',
  }
  const cls = classMap[value] ?? 'bg-gray-100 text-gray-700 border-gray-300'
  const description = VALUE_DESCRIPTIONS[value]
  const badge = (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-xs font-medium ${cls}`}>
      {value}
    </span>
  )
  if (!description) return badge
  return (
    <Tooltip>
      <TooltipTrigger>{badge}</TooltipTrigger>
      <TooltipContent>{description}</TooltipContent>
    </Tooltip>
  )
}

function ProgressBar({ value, label }: { value: number | null | undefined; label: string }) {
  const pct = value != null ? Math.round(value * 100) : 0
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
        />
      </div>
      <span className="text-xs text-muted-foreground tabular-nums">{pct}%</span>
    </div>
  )
}

export function VerdictRow({ row, aiExplanation }: VerdictRowProps) {
  const colorSymbol = getColorSymbol(row.composition_color)
  const colorClass = getColorClass(row.composition_color)

  return (
    <tr className="border-b border-border hover:bg-muted/30 transition-colors">
      {/* Condition */}
      <td className="px-3 py-2 align-top">
        <div className="flex flex-col gap-0.5">
          {getConditionDescription(row.condition_code) ? (
            <Tooltip>
              <TooltipTrigger className="font-mono text-xs font-medium cursor-help underline decoration-dotted">
                {row.condition_code}
              </TooltipTrigger>
              <TooltipContent>{getConditionDescription(row.condition_code)}</TooltipContent>
            </Tooltip>
          ) : (
            <code className="font-mono text-xs font-medium">{row.condition_code}</code>
          )}
          <span className="text-xs text-muted-foreground">{row.condition_label_sk}</span>
        </div>
      </td>

      {/* Value */}
      <td className="px-3 py-2 align-top">
        <ValueBadge value={row.value} />
      </td>

      {/* Confidence */}
      <td className="px-3 py-2 align-top">
        <ProgressBar value={row.confidence} label="Dôvera" />
      </td>

      {/* Completeness */}
      <td className="px-3 py-2 align-top">
        <ProgressBar value={row.data_completeness} label="Úplnosť dát" />
      </td>

      {/* Semafor */}
      <td className="px-3 py-2 align-top">
        <span
          className={`inline-flex h-6 w-6 items-center justify-center rounded border text-xs font-bold ${colorClass}`}
          aria-label={row.composition_color ?? 'NONE'}
          title={row.composition_color ?? 'NONE'}
        >
          {colorSymbol}
        </span>
      </td>

      {/* Flags */}
      <td className="px-3 py-2 align-top">
        <div className="flex flex-wrap gap-1">
          {row.is_illustrative && (
            <Badge variant="outline" className="text-xs py-0">ILUSTR.</Badge>
          )}
          {row.is_proxy && (
            <Badge variant="outline" className="text-xs py-0">PROXY</Badge>
          )}
          {row.is_mock && (
            <Badge variant="outline" className="text-xs py-0">MOCK</Badge>
          )}
        </div>
      </td>

      {/* Evidence */}
      <td className="px-3 py-2 align-top max-w-xs">
        {row.evidence_public_text ? (
          <details className="text-xs">
            <summary className="cursor-pointer text-primary hover:underline">Dôkaz</summary>
            <div className="mt-1 text-muted-foreground whitespace-pre-wrap leading-relaxed">
              {row.evidence_public_text}
            </div>
            <div className="mt-1">
              <ProvenanceLink url={row.provenance_source} />
            </div>
            {aiExplanation && <AiExplanation text={aiExplanation} />}
          </details>
        ) : aiExplanation ? (
          <details className="text-xs">
            <summary className="cursor-pointer text-primary hover:underline">Vysvetlenie</summary>
            <AiExplanation text={aiExplanation} />
          </details>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  )
}
