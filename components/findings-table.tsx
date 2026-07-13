'use client'

import { Fragment, useEffect, useState } from 'react'
import Link from 'next/link'
import type { FindingPublic } from '@/lib/supabase/types'
import { getSeverityClass, getSeverityLabel } from '@/lib/format/severity'
import { relativeTime } from '@/lib/format/dates'
import { EVIDENCE_TRAIL_LABELS_SK, getConditionLabel } from '@/lib/compliance/labels'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDemoMode } from '@/lib/demo-mode/context'

interface FindingsTableProps {
  findings: FindingPublic[]
  totalCount: number
  page: number
  pageSize: number
  /** Active filter params (severity/status/condition/scenario) so pagination keeps them. */
  filterQuery?: string
}

// Same DEMO provenance tag as district detail (components/district-findings.tsx)
// — demo scenarios must never read as live findings.
function DemoBadge() {
  return (
    <span
      className="inline-flex items-center rounded border border-amber-300 bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-800"
      title="Ukážkové (DEMO) dáta — ilustrácia scenára, nevstupuje do zákonného verdiktu"
    >
      DEMO
    </span>
  )
}

// VLA-15 — "Ako sme na to prišli": the evidence trail of a street-level
// verdict (VZN citation, register state, geometry, conclusion) + the
// source/method provenance every finding must carry. A verdict without
// visible reasoning must not be presented as an assertion (client 2026-07-06).
function EvidenceTrail({ finding }: { finding: FindingPublic }) {
  const trail = finding.evidence_trail
  const hasProvenance = Boolean(finding.source_public || finding.method_public)
  if (!trail && !hasProvenance) return null
  const L = EVIDENCE_TRAIL_LABELS_SK
  const rows: Array<[string, string | null | undefined]> = [
    [L.vzn_citation, trail?.vzn_citation],
    [L.register_state, trail?.register_state],
    [L.geometry_evidence, trail?.geometry_evidence],
    [L.conclusion_sk, trail?.conclusion_sk],
  ]
  return (
    <div className="mt-3 rounded-md border border-border bg-background p-3 space-y-2" data-testid="evidence-trail">
      <p className="text-xs font-semibold text-foreground">{L.heading}</p>
      {rows.map(([label, text]) =>
        text ? (
          <div key={label} className="text-xs leading-relaxed">
            <span className="font-medium text-foreground">{label}: </span>
            <span className="text-muted-foreground whitespace-pre-wrap">{text}</span>
          </div>
        ) : null
      )}
      {hasProvenance && (
        <p className="text-xs text-muted-foreground border-t border-border pt-2">
          {finding.source_public && (
            <>
              {L.source}: {finding.source_public}
            </>
          )}
          {finding.source_public && finding.method_public && ' · '}
          {finding.method_public && (
            <>
              {L.method}: {finding.method_public}
            </>
          )}
        </p>
      )}
    </div>
  )
}

const STATUS_LABELS: Record<string, string> = {
  open: 'Otvorený',
  acknowledged: 'Zaznamenaný',
  resolved: 'Vyriešený',
  wont_fix: 'Neopravovať',
}

export function FindingsTable({ findings, totalCount, page, pageSize, filterQuery }: FindingsTableProps) {
  const { demoMode } = useDemoMode()
  // VLA-34: real-only mode drops every is_demo=true finding client-side, off
  // the already-fetched page — no refetch. totalCount/pagination still come
  // from the server's unfiltered count (a second server round-trip just to
  // recompute pagination for the toggle flip is what the ticket says to
  // avoid), so the summary line below says so explicitly in real-only mode
  // instead of implying start–end/totalCount still matches what's on screen.
  const visibleFindings = demoMode ? findings : findings.filter((f) => !f.is_demo)
  const [openId, setOpenId] = useState<string | null>(null)

  // Deep link from the map legend: /findings#f-<finding_id> auto-expands the
  // trail of that finding and scrolls it into view (VLA-15).
  useEffect(() => {
    const hash = window.location.hash
    if (!hash.startsWith('#f-')) return
    const id = hash.slice(3)
    if (findings.some((f) => f.finding_id === id)) {
      setOpenId(id)
      document.getElementById(`f-${id}`)?.scrollIntoView({ block: 'center' })
    }
    // findings change only with server-side navigation; run once per mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const pageHref = (p: number) => {
    const params = new URLSearchParams(filterQuery)
    params.set('page', String(p))
    return `/findings?${params.toString()}`
  }

  if (visibleFindings.length === 0) {
    return (
      <div className="rounded-lg border border-border p-8 text-center text-sm text-muted-foreground">
        Žiadne nálezy pre tieto filtre.
      </div>
    )
  }

  const totalPages = Math.ceil(totalCount / pageSize)
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, totalCount)

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {demoMode
          ? `Zobrazujem ${start}–${end} z ${totalCount} nálezov`
          : `Zobrazujem ${visibleFindings.length} reálnych nálezov na tejto strane (len reálne dáta — DEMO záznamy skryté)`}
      </p>

      {/* Card stack — only on xs (< sm, < 640px). Tapping a card expands the
          full reason inline; the district link stays a separate control. */}
      <div className="block sm:hidden space-y-2">
        {visibleFindings.map((finding) => {
          const open = openId === finding.finding_id
          return (
            <div
              key={finding.finding_id}
              id={`f-${finding.finding_id}`}
              className="rounded-lg border border-border p-3 space-y-1.5 bg-background cursor-pointer hover:bg-muted/30 transition-colors"
              onClick={() => setOpenId(open ? null : finding.finding_id)}
              role="button"
              tabIndex={0}
              aria-expanded={open}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpenId(open ? null : finding.finding_id) } }}
              aria-label={`Nález pre obvod ${finding.district_name}`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${getSeverityClass(finding.severity)}`}
                  >
                    {getSeverityLabel(finding.severity)}
                  </span>
                  {finding.is_demo && <DemoBadge />}
                </span>
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {STATUS_LABELS[finding.status] ?? finding.status}
                </span>
              </div>
              <div>
                <Link
                  href={`/districts/${finding.district_id}`}
                  className="text-sm font-medium text-primary underline hover:text-primary/80"
                  onClick={(e) => e.stopPropagation()}
                >
                  {finding.district_name}
                </Link>
                {finding.municipality_name && (
                  <p className="text-xs text-muted-foreground">{finding.municipality_name}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <code className="font-mono text-xs">{finding.condition_code}</code>
                <p className="text-xs text-muted-foreground">
                  {getConditionLabel(finding.condition_code)}
                </p>
              </div>
              {finding.evidence_public_text && (
                <p className={`text-xs text-muted-foreground ${open ? 'whitespace-pre-wrap' : 'line-clamp-2'}`}>
                  {finding.evidence_public_text}
                </p>
              )}
              {open && <EvidenceTrail finding={finding} />}
              <p className="text-xs text-muted-foreground">
                {relativeTime(finding.created_at)}
              </p>
            </div>
          )
        })}
      </div>

      {/* Table — sm and above. The whole row is clickable; the reason expands
          FULL-WIDTH BELOW the row (no page jump). A narrow "Dôkaz" column is
          replaced by an expand affordance + an inline full-width detail row. */}
      <div className="hidden sm:block overflow-x-auto rounded-lg border border-border">
        <Table aria-label="Register nálezov">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs sticky left-0 bg-background z-10">Závažnosť</TableHead>
              <TableHead className="text-xs">Obec</TableHead>
              <TableHead className="text-xs">Obvod</TableHead>
              <TableHead className="text-xs">Podmienka</TableHead>
              <TableHead className="text-xs">Stav</TableHead>
              <TableHead className="text-xs">Vytvorený</TableHead>
              <TableHead className="text-xs">Dôvod</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleFindings.map((finding) => {
              const open = openId === finding.finding_id
              const hasReason = Boolean(
                finding.evidence_public_text || finding.evidence_trail ||
                finding.source_public || finding.method_public
              )
              return (
                <Fragment key={finding.finding_id}>
                  <TableRow
                    id={`f-${finding.finding_id}`}
                    className={`cursor-pointer hover:bg-muted/30 transition-colors ${open ? 'bg-muted/30' : ''}`}
                    onClick={() => hasReason && setOpenId(open ? null : finding.finding_id)}
                    onKeyDown={(e) => { if (hasReason && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); setOpenId(open ? null : finding.finding_id) } }}
                    tabIndex={hasReason ? 0 : undefined}
                    role={hasReason ? 'button' : undefined}
                    aria-expanded={hasReason ? open : undefined}
                    aria-label={`Nález pre obvod ${finding.district_name}`}
                  >
                    <TableCell className="sticky left-0 bg-background z-10">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${getSeverityClass(finding.severity)}`}
                        >
                          {getSeverityLabel(finding.severity)}
                        </span>
                        {finding.is_demo && <DemoBadge />}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">{finding.municipality_name ?? '—'}</TableCell>
                    <TableCell className="text-xs">
                      <Link
                        href={`/districts/${finding.district_id}`}
                        className="text-primary underline hover:text-primary/80"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {finding.district_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs">
                      <div className="flex items-center gap-1.5">
                        <code className="font-mono text-xs">{finding.condition_code}</code>
                      </div>
                      <span className="block text-muted-foreground text-xs">
                        {getConditionLabel(finding.condition_code)}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs whitespace-nowrap overflow-hidden">
                      {STATUS_LABELS[finding.status] ?? finding.status}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap overflow-hidden">
                      {relativeTime(finding.created_at)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {hasReason ? (
                        <span className="inline-flex items-center gap-1 text-primary">
                          <span aria-hidden className={`transition-transform ${open ? 'rotate-90' : ''}`}>▸</span>
                          {open ? 'Skryť' : 'Zobraziť'}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                  {hasReason && open && (
                    <TableRow className="bg-muted/20 hover:bg-muted/20">
                      <TableCell colSpan={7} className="px-4 py-3">
                        {finding.evidence_public_text && (
                          <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">
                            {finding.evidence_public_text}
                          </p>
                        )}
                        <EvidenceTrail finding={finding} />
                        {finding.is_demo && (
                          <p className="mt-2 text-xs text-amber-800">
                            Ukážkové (DEMO) dáta — ilustrácia scenára, nevstupuje do zákonného verdiktu.
                          </p>
                        )}
                        <Link
                          href={`/districts/${finding.district_id}`}
                          className="mt-2 inline-block text-xs text-primary underline hover:text-primary/80"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Otvoriť detail obvodu →
                        </Link>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex gap-2 items-center text-xs">
          {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map((p) => (
            <Link
              key={p}
              href={pageHref(p)}
              className={`rounded px-2 py-1 border ${p === page ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted'}`}
              aria-current={p === page ? 'page' : undefined}
            >
              {p}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
