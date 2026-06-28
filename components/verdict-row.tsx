'use client'

import { useId, useState } from 'react'
import type { DistrictScorecardRow } from '@/lib/supabase/types'
import { getColorClass, getColorSymbol, valueToColor, isOutsideSemafor, isSemaforApplicable, getValueLabel } from '@/lib/compliance/colors'
import { getConditionDescription } from '@/lib/compliance/labels'
import { ProvenanceLink } from './provenance-link'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'

interface VerdictRowProps {
  row: DistrictScorecardRow
}

const VALUE_DESCRIPTIONS: Record<string, string> = {
  PASS:              'Podmienka je splnená. Dostupné dáta nenašli žiadny problém.',
  FAIL:              'Podmienka nie je splnená. Zákonná požiadavka nie je dodržaná.',
  INCOMPLETE:        'Chýbajú vstupné dáta, preto výsledok zatiaľ nevieme určiť.',
  RISK:              'Indikátor upozorňuje na možný problém, ktorý stojí za bližšiu kontrolu.',
  INSUFFICIENT_DATA: 'Dát je príliš málo na to, aby mal výsledok dostatočnú výpovednú hodnotu.',
  // SIGNAL is a soft risk indicator for the "mäkké" indicators that § 44 NEEN
  // numerates as hard conditions (sociálny kontext / MRK = P-e, demografia = P-f).
  // It flags a risk worth a closer look; it is explicitly NOT a PASS/FAIL verdict
  // and never drives the legal semafor.
  SIGNAL:            'Upozornenie, nie verdikt. Ukazuje na možné riziko v oblasti, ktorú zákon § 44 priamo nehodnotí (sociálny kontext, demografia, jazyk). Nie je to PASS ani FAIL — len podnet na bližšie preskúmanie.',
  // NO_SIGNAL = evaluated, no issue found in a non-§44 (mimo semaforu) oblasti.
  NO_SIGNAL:         'Vyhodnotené — bez podnetu. V tejto oblasti mimo § 44 (sociálny kontext, demografia, jazyk) sa nenašiel žiadny problém. Nevstupuje do zákonného semaforu.',
  NOT_EVALUATED:     'Údaj sa zatiaľ nedal vyhodnotiť. Oblasť je mimo zákonného semaforu § 44.',
}

function ValueBadge({ value }: { value: string }) {
  const classMap: Record<string, string> = {
    PASS:              'bg-green-100 text-green-800 border-green-300',
    FAIL:              'bg-red-100 text-red-800 border-red-300',
    INCOMPLETE:        'bg-yellow-100 text-yellow-800 border-yellow-300',
    RISK:              'bg-orange-100 text-orange-800 border-orange-300',
    INSUFFICIENT_DATA: 'bg-blue-100 text-blue-800 border-blue-300',
    // Violet = soft "signal" indicator, visually distinct from the
    // green/red/orange PASS-FAIL-RISK family so it never reads as a verdict.
    SIGNAL:            'bg-violet-100 text-violet-800 border-violet-300',
    // Evaluated "no issue" (mimo semaforu) and not-evaluated read as neutral
    // slate — clearly decisive but visibly outside the traffic light.
    NO_SIGNAL:         'bg-slate-100 text-slate-700 border-slate-300',
    NOT_EVALUATED:     'bg-slate-100 text-slate-600 border-slate-300',
  }
  const cls = classMap[value] ?? 'bg-gray-100 text-gray-700 border-gray-300'
  const description = VALUE_DESCRIPTIONS[value]
  // SIGNAL is non-obvious to a lay reader, so render a small "signál" hint next
  // to the friendly value to nudge them to the explanatory tooltip.
  const isSignal = value === 'SIGNAL'
  const badge = (
    <span className="inline-flex items-center gap-1">
      <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${cls}`}>
        {getValueLabel(value)}
      </span>
      {isSignal && (
        <span className="text-[10px] font-medium text-violet-700">(signál, nie verdikt)</span>
      )}
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

export function VerdictRow({ row }: VerdictRowProps) {
  // The per-row semafor reflects THIS condition's own verdict (row.value), not
  // the district-wide composition_color — so on a RED district a PASS row shows
  // a green ✓, not a red ✕. A row is "mimo semaforu" when EITHER its condition is
  // outside the § 44 traffic light by group (JAZYK / Pe / Pf — item 8a, data-driven
  // via isSemaforApplicable, no JAZYK hardcode) OR its value is a non-verdict
  // (SIGNAL / NO_SIGNAL / NOT_EVALUATED). Those get a neutral "—" dash.
  const outsideSemafor = !isSemaforApplicable(row.condition_code) || isOutsideSemafor(row.value)
  const rowColor = valueToColor(row.value)
  const colorSymbol = getColorSymbol(rowColor)
  const colorClass = getColorClass(rowColor)
  const detailId = useId()
  const [open, setOpen] = useState(false)

  // The row carries detail only when there is evidence text to show; otherwise
  // it stays static (nothing to expand).
  const hasDetail = Boolean(row.evidence_public_text)

  function toggle() {
    if (hasDetail) setOpen((v) => !v)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTableRowElement>) {
    if (!hasDetail) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setOpen((v) => !v)
    }
  }

  return (
    <>
      <tr
        className={`border-b border-border transition-colors ${hasDetail ? 'cursor-pointer hover:bg-muted/40' : 'hover:bg-muted/30'} ${open ? 'bg-muted/30' : ''}`}
        onClick={toggle}
        onKeyDown={onKeyDown}
        tabIndex={hasDetail ? 0 : undefined}
        role={hasDetail ? 'button' : undefined}
        aria-expanded={hasDetail ? open : undefined}
        aria-controls={hasDetail ? detailId : undefined}
      >
        {/* Condition */}
        <td className="px-3 py-2 align-top">
          <div className="flex flex-col gap-0.5">
            {getConditionDescription(row.condition_code) ? (
              <Tooltip>
                {/* stopPropagation so opening the tooltip does not toggle the row */}
                <TooltipTrigger
                  onClick={(e) => e.stopPropagation()}
                  className="font-mono text-xs font-medium cursor-help underline decoration-dotted text-left"
                >
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

        {/* Value (REAL verdict) */}
        <td className="px-3 py-2 align-top">
          <div className="flex flex-col">
            <ValueBadge value={row.value} />
          </div>
        </td>

        {/* Confidence */}
        <td className="px-3 py-2 align-top">
          <ProgressBar value={row.confidence} label="Dôvera" />
        </td>

        {/* Completeness */}
        <td className="px-3 py-2 align-top">
          <ProgressBar value={row.data_completeness} label="Úplnosť dát" />
        </td>

        {/* Semafor — reflects THIS condition's own verdict (row.value). Language
            and SIGNAL/NOT_EVALUATED conditions are outside the § 44 traffic
            light, so they show a neutral "mimo semaforu" dash, never a red ✕. */}
        <td className="px-3 py-2 align-top">
          {outsideSemafor ? (
            <span
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-gray-300 bg-gray-50 text-xs font-bold text-gray-400"
              aria-label="mimo semaforu"
              title="Mimo semaforu § 44 — nevstupuje do zákonného verdiktu"
            >
              —
            </span>
          ) : (
            <span
              className={`inline-flex h-6 w-6 items-center justify-center rounded border text-xs font-bold ${colorClass}`}
              aria-label={rowColor}
              title={rowColor}
            >
              {colorSymbol}
            </span>
          )}
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
          </div>
        </td>

        {/* Detail toggle affordance — the whole row is clickable, this just
            signals it and stays keyboard-reachable as a redundant control. */}
        <td className="px-3 py-2 align-top max-w-xs">
          {hasDetail ? (
            <span className="inline-flex items-center gap-1 text-xs text-primary">
              <span aria-hidden className={`transition-transform ${open ? 'rotate-90' : ''}`}>▸</span>
              Detail
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </td>
      </tr>

      {/* Expanded detail row — spans the full table width */}
      {hasDetail && open && (
        <tr id={detailId} className="border-b border-border bg-muted/20">
          <td colSpan={7} className="px-3 py-2.5">
            {row.evidence_public_text && (
              <div className="text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">
                {row.evidence_public_text}
              </div>
            )}
            {row.provenance_source && (
              <div className="mt-1">
                <ProvenanceLink url={row.provenance_source} />
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}
