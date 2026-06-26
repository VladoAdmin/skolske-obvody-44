'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useCallback } from 'react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { CONDITION_LABELS_SK } from '@/lib/compliance/labels'

const ALL = '__all__'

// Explicit SK label maps so the trigger always shows Slovak regardless of
// base-ui SelectValue behaviour with controlled values (bod 8a fix).
const SEVERITY_SK: Record<string, string> = {
  critical: 'Kritická',
  high: 'Vysoká',
  medium: 'Stredná',
  low: 'Nízka',
  info: 'Informácia',
}

const STATUS_SK: Record<string, string> = {
  open: 'Otvorený',
  acknowledged: 'Zaznamenaný',
  resolved: 'Vyriešený',
  wont_fix: 'Neopravovať',
}

export function FindingsFilters() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const updateParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value === ALL) {
        params.delete(key)
      } else {
        params.set(key, value)
      }
      params.delete('page') // reset to page 1 on filter change
      router.push(`/findings?${params.toString()}`, { scroll: false })
    },
    [router, searchParams]
  )

  const severity = searchParams.get('severity') ?? ALL
  const status = searchParams.get('status') ?? ALL
  const condition = searchParams.get('condition') ?? ALL

  // Derive the SK label to show in the trigger (fallback to placeholder when ALL).
  const severityLabel = severity !== ALL ? (SEVERITY_SK[severity] ?? severity) : undefined
  const statusLabel = status !== ALL ? (STATUS_SK[status] ?? status) : undefined
  const conditionLabel = condition !== ALL ? (CONDITION_LABELS_SK[condition]?.label ?? condition) : undefined

  return (
    <div className="flex flex-col sm:flex-row sm:flex-wrap gap-3" role="search" aria-label="Filtre nálezov">
      {/* Severity filter */}
      <div className="sm:w-auto w-full">
        <label htmlFor="filter-severity" className="text-xs text-muted-foreground block mb-1">Závažnosť</label>
        <Select value={severity !== ALL ? severity : undefined} onValueChange={(v: string | null) => updateParam('severity', v ?? ALL)}>
          <SelectTrigger id="filter-severity" className="w-full sm:w-40 h-8 text-xs">
            <SelectValue placeholder="Všetky závažnosti">
              {severityLabel}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Všetky závažnosti</SelectItem>
            <SelectItem value="critical">Kritická</SelectItem>
            <SelectItem value="high">Vysoká</SelectItem>
            <SelectItem value="medium">Stredná</SelectItem>
            <SelectItem value="low">Nízka</SelectItem>
            <SelectItem value="info">Informácia</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Status filter */}
      <div className="sm:w-auto w-full">
        <label htmlFor="filter-status" className="text-xs text-muted-foreground block mb-1">Stav</label>
        <Select value={status !== ALL ? status : undefined} onValueChange={(v: string | null) => updateParam('status', v ?? ALL)}>
          <SelectTrigger id="filter-status" className="w-full sm:w-36 h-8 text-xs">
            <SelectValue placeholder="Všetky stavy">
              {statusLabel}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Všetky stavy</SelectItem>
            <SelectItem value="open">Otvorený</SelectItem>
            <SelectItem value="acknowledged">Zaznamenaný</SelectItem>
            <SelectItem value="resolved">Vyriešený</SelectItem>
            <SelectItem value="wont_fix">Neopravovať</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Condition filter */}
      <div className="sm:w-auto w-full">
        <label htmlFor="filter-condition" className="text-xs text-muted-foreground block mb-1">Podmienka</label>
        <Select value={condition !== ALL ? condition : undefined} onValueChange={(v: string | null) => updateParam('condition', v ?? ALL)}>
          <SelectTrigger id="filter-condition" className="w-full sm:w-52 h-8 text-xs">
            <SelectValue placeholder="Všetky podmienky">
              {conditionLabel}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Všetky podmienky</SelectItem>
            {Object.entries(CONDITION_LABELS_SK)
              .sort((a, b) => a[1].order - b[1].order)
              .map(([code, { label }]) => (
                <SelectItem key={code} value={code}>{label}</SelectItem>
              ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
