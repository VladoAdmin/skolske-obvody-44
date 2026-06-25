// Condition code → SK label + sort order — mirrors SQL CASE in district_scorecard view
// Used as fallback/TS safety net when view column is unavailable

export const CONDITION_LABELS_SK: Record<string, { label: string; order: number }> = {
  S1: { label: 'Š1 — Adresy žiakov a obvod', order: 1 },
  S2: { label: 'Š2 — Topologické pokrytie', order: 2 },
  S3: { label: 'Š3 — Kompozícia obvodu', order: 3 },
  Pa: { label: 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km', order: 4 },
  Pb: { label: 'P-b — Pešia trasa', order: 5 },
  Pc: { label: 'P-c — MHD dostupnosť', order: 6 },
  Pd: { label: 'P-d — Bariéry (cesty, koľaje)', order: 7 },
  Pe: { label: 'P-e — Sociálny kontext (Atlas MRK)', order: 8 },
  Pf: { label: 'P-f — Demografia detí', order: 9 },
}

export function getConditionLabel(code: string): string {
  return CONDITION_LABELS_SK[code]?.label ?? code
}

export function getConditionOrder(code: string): number {
  return CONDITION_LABELS_SK[code]?.order ?? 99
}
