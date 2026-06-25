'use client'

import Link from 'next/link'
import type { FindingPublic } from '@/lib/supabase/types'
import { getSeverityClass, getSeverityLabel } from '@/lib/format/severity'
import { relativeTime } from '@/lib/format/dates'
import { getConditionLabel } from '@/lib/compliance/labels'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface FindingsTableProps {
  findings: FindingPublic[]
  totalCount: number
  page: number
  pageSize: number
}

const STATUS_LABELS: Record<string, string> = {
  open: 'Otvorený',
  acknowledged: 'Zaznamenaný',
  resolved: 'Vyriešený',
  wont_fix: 'Neopravovať',
}

export function FindingsTable({ findings, totalCount, page, pageSize }: FindingsTableProps) {
  if (findings.length === 0) {
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
        Zobrazujem {start}–{end} z {totalCount} nálezov
      </p>

      {/* Card stack — only on xs (< sm, < 640px) */}
      <div className="block sm:hidden space-y-2">
        {findings.map((finding) => (
          <div
            key={finding.finding_id}
            className="rounded-lg border border-border p-3 space-y-1.5 bg-background"
          >
            <div className="flex items-start justify-between gap-2">
              <span
                className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${getSeverityClass(finding.severity)}`}
              >
                {getSeverityLabel(finding.severity)}
              </span>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {STATUS_LABELS[finding.status] ?? finding.status}
              </span>
            </div>
            <div>
              <Link
                href={`/districts/${finding.district_id}`}
                className="text-sm font-medium text-primary underline hover:text-primary/80"
              >
                {finding.district_name}
              </Link>
              {finding.municipality_name && (
                <p className="text-xs text-muted-foreground">{finding.municipality_name}</p>
              )}
            </div>
            <div>
              <code className="font-mono text-xs">{finding.condition_code}</code>
              <p className="text-xs text-muted-foreground">
                {getConditionLabel(finding.condition_code)}
              </p>
            </div>
            {finding.evidence_public_text && (
              <p className="text-xs text-muted-foreground line-clamp-2">
                {finding.evidence_public_text}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              {relativeTime(finding.created_at)}
            </p>
          </div>
        ))}
      </div>

      {/* Table — sm and above */}
      <div className="hidden sm:block overflow-x-auto rounded-lg border border-border">
        <Table aria-label="Register nálezov">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs sticky left-0 bg-background z-10">Závažnosť</TableHead>
              <TableHead className="text-xs">Obec</TableHead>
              <TableHead className="text-xs">Obvod</TableHead>
              <TableHead className="text-xs">Podmienka</TableHead>
              <TableHead className="text-xs">Dôkaz</TableHead>
              <TableHead className="text-xs">Stav</TableHead>
              <TableHead className="text-xs">Vytvorený</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {findings.map((finding) => (
              <TableRow
                key={finding.finding_id}
                className="cursor-pointer hover:bg-muted/30 transition-colors"
                onClick={() => {}}
                aria-label={`Nález pre obvod ${finding.district_name}`}
              >
                <TableCell className="sticky left-0 bg-background z-10">
                  <span
                    className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${getSeverityClass(finding.severity)}`}
                  >
                    {getSeverityLabel(finding.severity)}
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
                  <code className="font-mono text-xs">{finding.condition_code}</code>
                  <span className="block text-muted-foreground text-xs">
                    {getConditionLabel(finding.condition_code)}
                  </span>
                </TableCell>
                <TableCell className="max-w-[300px] text-xs text-muted-foreground truncate overflow-hidden whitespace-nowrap">
                  <span title={finding.evidence_public_text ?? undefined}>
                    {finding.evidence_public_text ?? '—'}
                  </span>
                </TableCell>
                <TableCell className="text-xs whitespace-nowrap overflow-hidden">
                  {STATUS_LABELS[finding.status] ?? finding.status}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground whitespace-nowrap overflow-hidden">
                  {relativeTime(finding.created_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex gap-2 items-center text-xs">
          {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map((p) => (
            <Link
              key={p}
              href={`/findings?page=${p}`}
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
