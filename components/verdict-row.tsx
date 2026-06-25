import type { DistrictScorecardRow } from '@/lib/supabase/types'
import { getColorClass, getColorSymbol } from '@/lib/compliance/colors'
import { ProvenanceLink } from './provenance-link'
import { Badge } from '@/components/ui/badge'

interface VerdictRowProps {
  row: DistrictScorecardRow
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
  return (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-xs font-medium ${cls}`}>
      {value}
    </span>
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

export function VerdictRow({ row }: VerdictRowProps) {
  const colorSymbol = getColorSymbol(row.composition_color)
  const colorClass = getColorClass(row.composition_color)

  return (
    <tr className="border-b border-border hover:bg-muted/30 transition-colors">
      {/* Condition */}
      <td className="px-3 py-2 align-top">
        <div className="flex flex-col gap-0.5">
          <code className="font-mono text-xs font-medium">{row.condition_code}</code>
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
          </details>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  )
}
