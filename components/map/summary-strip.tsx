import type { DistrictMapFeature, SoFindingsPanelItem } from '@/lib/supabase/types'
import type { CompositionColor } from '@/lib/compliance/colors'

interface SummaryStripProps {
  features: DistrictMapFeature[]
  findings: SoFindingsPanelItem[]
}

const SEMAFOR: { color: CompositionColor; emoji: string; label: string }[] = [
  { color: 'RED', emoji: '🔴', label: 'Nesúlad' },
  { color: 'ORANGE', emoji: '🟠', label: 'Čiastočne' },
  { color: 'GREEN', emoji: '🟢', label: 'V súlade' },
  { color: 'NONE', emoji: '⚪', label: 'Nezhodnotené' },
]

/**
 * High-level pilot summary, rendered first on /map. Counts are derived from the
 * already-fetched features (composition_color) and findings — no extra queries.
 * Designed to fit above the fold on a 375×812 phone.
 */
export function SummaryStrip({ features, findings }: SummaryStripProps) {
  const counts: Record<CompositionColor, number> = { RED: 0, ORANGE: 0, GREEN: 0, NONE: 0 }
  for (const f of features) {
    const c = (f.composition_color as CompositionColor) ?? 'NONE'
    counts[c in counts ? c : 'NONE'] += 1
  }

  return (
    <section
      aria-label="Súhrnný prehľad pilotu"
      className="rounded-lg border border-border bg-card p-3"
    >
      <div className="flex flex-wrap items-stretch gap-2">
        {/* Semafor breakdown */}
        <ul className="flex flex-1 min-w-0 items-center justify-around gap-1 list-none p-0 m-0">
          {SEMAFOR.map(({ color, emoji, label }) => (
            <li key={color} className="flex flex-col items-center px-1">
              <span className="text-lg leading-none" aria-hidden="true">
                {emoji}
              </span>
              <span className="text-base font-semibold tabular-nums leading-tight mt-0.5">
                {counts[color]}
              </span>
              <span className="text-[10px] text-muted-foreground leading-tight">{label}</span>
            </li>
          ))}
        </ul>

        {/* Divider on wider screens */}
        <div className="hidden sm:block w-px bg-border" aria-hidden="true" />

        {/* Aggregate counts */}
        <dl className="flex items-center justify-around gap-3 sm:gap-4 list-none m-0 px-1">
          <div className="flex flex-col items-center">
            <dt className="text-[10px] text-muted-foreground leading-tight order-2">Obvodov</dt>
            <dd className="text-base font-semibold tabular-nums leading-tight m-0 order-1">
              {features.length}
            </dd>
          </div>
          <div className="flex flex-col items-center">
            <dt className="text-[10px] text-muted-foreground leading-tight order-2">
              Otvorených nálezov
            </dt>
            <dd className="text-base font-semibold tabular-nums leading-tight m-0 order-1">
              {findings.length}
            </dd>
          </div>
        </dl>
      </div>
    </section>
  )
}
