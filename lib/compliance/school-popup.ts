// Shared builder for the school-pin click popup used on both the region map
// and the district detail map. Produces plain HTML for Leaflet bindPopup.
//
// For a district-linked (public VZN) school the popup shows: school name, the
// semafor (composition_color → symbol + label), a compact per-§44-condition
// status list with PASS/FAIL/INCOMPLETE counts + open-findings count, and a
// link to the district detail page.
// For a private / non-VZN school it shows: name + founder + a clear "no VZN
// obvod / not evaluated" note (no fake semafor).

import type { DistrictScorecardRow } from '@/lib/supabase/types'
import { getColorSymbol, getColorLabel } from './colors'

// Compact per-district summary derived server-side from so_district_scorecard
// + so_findings_panel and passed to the client map keyed by district_id.
export interface DistrictPopupSummary {
  composition_color: string | null
  // Per-condition rows (label + value/status + confidence%) in display order.
  conditions: { label: string; value: string; confidence: number | null }[]
  passCount: number
  failCount: number
  incompleteCount: number
  openFindingsCount: number
  // Multi-part geometry review flag (Task B): present only when the obvod is
  // composed of >1 separated polygon part after sliver cleanup.
  multiPart?: { parts: number; biggestKm2: number; otherKm2: number[] }
}

// Per-district multi-part info derived from island rows: parts count + each
// real (non-demo) part's area in km², largest first.
export type MultiPartByDistrict = Record<
  string,
  { parts: number; biggestKm2: number; otherKm2: number[] }
>

// Build multiPartByDistrict from raw island rows. A district is multi-part when
// it has >1 real (non-demo) part. area_m2 is per-part.
export function buildMultiPartByDistrict(
  islandRows: { district_id: string; area_m2: number | null; is_demo?: boolean }[]
): MultiPartByDistrict {
  const byDistrict = new Map<string, number[]>()
  for (const r of islandRows) {
    if (r.is_demo === true) continue
    const list = byDistrict.get(r.district_id) ?? []
    list.push((r.area_m2 ?? 0) / 1_000_000)
    byDistrict.set(r.district_id, list)
  }
  const out: MultiPartByDistrict = {}
  byDistrict.forEach((areas, districtId) => {
    if (areas.length <= 1) return
    const sorted = [...areas].sort((a, b) => b - a)
    out[districtId] = {
      parts: sorted.length,
      biggestKm2: sorted[0],
      otherKm2: sorted.slice(1),
    }
  })
  return out
}

// Build the summary map keyed by district_id from raw scorecard rows + findings.
export function buildDistrictSummaries(
  scorecardRows: DistrictScorecardRow[],
  openFindingsByDistrict: Record<string, number>,
  multiPartByDistrict: MultiPartByDistrict = {}
): Record<string, DistrictPopupSummary> {
  const byDistrict = new Map<string, DistrictScorecardRow[]>()
  for (const row of scorecardRows) {
    const list = byDistrict.get(row.district_id) ?? []
    list.push(row)
    byDistrict.set(row.district_id, list)
  }

  const summaries: Record<string, DistrictPopupSummary> = {}
  byDistrict.forEach((rows, districtId) => {
    const sorted = [...rows].sort((a, b) => (a.condition_order ?? 99) - (b.condition_order ?? 99))
    let passCount = 0
    let failCount = 0
    let incompleteCount = 0
    for (const r of sorted) {
      if (r.value === 'PASS') passCount++
      else if (r.value === 'FAIL') failCount++
      else incompleteCount++ // INCOMPLETE / RISK / INSUFFICIENT_DATA
    }
    summaries[districtId] = {
      composition_color: sorted[0]?.composition_color ?? null,
      conditions: sorted.map((r) => ({
        label: r.condition_label_sk,
        value: r.value,
        confidence: r.confidence,
      })),
      passCount,
      failCount,
      incompleteCount,
      openFindingsCount: openFindingsByDistrict[districtId] ?? 0,
      multiPart: multiPartByDistrict[districtId],
    }
  })

  // A multi-part district may have no scorecard rows yet — still surface the
  // geometry review flag in its popup.
  for (const [districtId, mp] of Object.entries(multiPartByDistrict)) {
    if (!summaries[districtId]) {
      summaries[districtId] = {
        composition_color: null,
        conditions: [],
        passCount: 0,
        failCount: 0,
        incompleteCount: 0,
        openFindingsCount: openFindingsByDistrict[districtId] ?? 0,
        multiPart: mp,
      }
    }
  }
  return summaries
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// Status → coloured dot for the per-condition list.
function valueDot(value: string): string {
  if (value === 'PASS') return '🟢'
  if (value === 'FAIL') return '🔴'
  return '🟡' // INCOMPLETE / RISK / INSUFFICIENT_DATA
}

// Popup for a district-linked (public VZN) school.
export function buildDistrictSchoolPopup(
  schoolName: string,
  districtId: string,
  summary: DistrictPopupSummary | undefined,
  compositionColorFallback: string | null
): string {
  const color = summary?.composition_color ?? compositionColorFallback
  const semaforSymbol = getColorSymbol(color)
  const semaforLabel = getColorLabel(color)

  const conditionsHtml = summary && summary.conditions.length > 0
    ? `<div style="margin-top:6px;display:grid;grid-template-columns:auto 1fr auto;gap:1px 6px;align-items:baseline">` +
      summary.conditions
        .map((c) => {
          const conf = c.confidence != null ? `${Math.round(c.confidence * 100)} %` : '—'
          return (
            `<span>${valueDot(c.value)}</span>` +
            `<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(c.label)}</span>` +
            `<span style="color:#6b7280;white-space:nowrap">${escapeHtml(c.value)} · ${conf}</span>`
          )
        })
        .join('') +
      `</div>`
    : ''

  const countsHtml = summary
    ? `<div style="margin-top:6px;font-size:11px;color:#374151">` +
      `🟢 ${summary.passCount} PASS · 🔴 ${summary.failCount} FAIL · 🟡 ${summary.incompleteCount} neúplné` +
      `<br/>Otvorené nálezy: <strong>${summary.openFindingsCount}</strong>` +
      `</div>`
    : `<div style="margin-top:6px;font-size:11px;color:#6b7280">Scorecard zatiaľ nedostupný pre tento obvod.</div>`

  // Multi-part geometry review flag (Task B): an obvod should be one contiguous
  // polygon; flag when it has separated parts that need a manual check.
  const mp = summary?.multiPart
  const multiPartHtml = mp
    ? `<div style="margin-top:6px;padding:5px 7px;border:1px solid #fcd34d;` +
      `background:#fffbeb;border-radius:4px;font-size:11px;color:#92400e;line-height:1.35">` +
      `⚠ Tento obvod má <strong>${mp.parts}</strong> oddelených častí — na kontrolu` +
      `<br/>najväčšia ${mp.biggestKm2.toFixed(2)} km²` +
      (mp.otherKm2.length > 0
        ? `, ostatné: ${mp.otherKm2.map((a) => `${a.toFixed(2)} km²`).join(', ')}`
        : '') +
      `</div>`
    : ''

  return (
    `<div style="min-width:200px;max-width:260px;font-size:12px;line-height:1.4">` +
    `<div style="font-weight:700">${escapeHtml(schoolName)}</div>` +
    `<div style="margin-top:4px">Semafor: <strong>${semaforSymbol} ${escapeHtml(semaforLabel)}</strong></div>` +
    countsHtml +
    multiPartHtml +
    conditionsHtml +
    `<div style="margin-top:8px">` +
    `<a href="/districts/${encodeURIComponent(districtId)}" style="color:#2563eb;font-weight:600;text-decoration:underline">Zobraziť detail obvodu →</a>` +
    `</div>` +
    `</div>`
  )
}

// Popup for a private / non-VZN school (no district, not evaluated).
export function buildNonVznSchoolPopup(
  schoolName: string,
  kind: string | null,
  isPrivate: boolean
): string {
  const founderLabel = isPrivate ? 'súkromná / cirkevná' : 'verejná (mesto Prešov)'
  return (
    `<div style="min-width:180px;max-width:260px;font-size:12px;line-height:1.4">` +
    `<div style="font-weight:700">${escapeHtml(schoolName)}${kind ? ` <span style="font-weight:400;color:#6b7280">(${escapeHtml(kind)})</span>` : ''}</div>` +
    `<div style="margin-top:4px">Zriaďovateľ: ${escapeHtml(founderLabel)}</div>` +
    `<div style="margin-top:6px;font-size:11px;color:#6b7280">Bez VZN obvodu — § 44 sa nehodnotí.</div>` +
    `</div>`
  )
}
