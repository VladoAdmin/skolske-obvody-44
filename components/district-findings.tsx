import type { SoFindingsPanelItem } from '@/lib/supabase/types'
import { getSeverityClass, getSeverityLabel } from '@/lib/format/severity'
import { ProvenanceLink } from './provenance-link'

interface DistrictFindingsProps {
  findings: SoFindingsPanelItem[]
}

// Explains each § 44 verdict shown in the scorecard with its engine finding:
// condition, severity and evidence text straight from so_findings_panel — no
// client-side severity/colour logic, same helpers the map legend (Checkpoint 2)
// uses. Demo scenarios stay visibly tagged so they never read as live findings.
export function DistrictFindings({ findings }: DistrictFindingsProps) {
  if (findings.length === 0) return null

  const sorted = [...findings].sort((a, b) => b.severity_rank - a.severity_rank)

  return (
    <section aria-labelledby="findings-heading">
      <h2 id="findings-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        Nálezy a dôkazy § 44
      </h2>
      <ul className="space-y-2">
        {sorted.map((f) => (
          <li key={f.finding_id} className="rounded-lg border border-border px-3 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-semibold ${getSeverityClass(f.severity)}`}
              >
                {getSeverityLabel(f.severity)}
              </span>
              {f.is_demo && (
                <span
                  className="inline-flex items-center rounded border border-amber-300 bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-800"
                  title="Ukážkové (DEMO) dáta — ilustrácia scenára, nevstupuje do zákonného verdiktu"
                >
                  DEMO
                </span>
              )}
              <span className="text-sm font-medium">{f.condition_label_sk}</span>
            </div>
            {f.evidence_public_text && (
              <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {f.evidence_public_text}
              </p>
            )}
            {f.provenance_source && (
              <div className="mt-1.5">
                <ProvenanceLink url={f.provenance_source} />
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
