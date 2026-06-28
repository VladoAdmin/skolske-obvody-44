// Semafor color → Tailwind class mapping + a11y non-color encoding

export type CompositionColor = 'RED' | 'ORANGE' | 'GREEN' | 'NONE'

export const COLOR_CLASSES: Record<CompositionColor, string> = {
  GREEN:  'bg-green-100 text-green-800 border-green-300',
  ORANGE: 'bg-orange-100 text-orange-800 border-orange-300',
  RED:    'bg-red-100 text-red-800 border-red-300',
  NONE:   'bg-gray-100 text-gray-600 border-gray-300',
}

export const COLOR_SYMBOL: Record<CompositionColor, string> = {
  GREEN:  '✓',
  ORANGE: '~',
  RED:    '✕',
  NONE:   '?',
}

export const COLOR_LABEL: Record<CompositionColor, string> = {
  GREEN:  'V súlade',
  ORANGE: 'Čiastočne',
  RED:    'Nesúlad',
  NONE:   'Nezhodnotené',
}

// Gov-style semafor ROW styling (minedu manual): a soft tint wash + a strong
// left bar + strong-coloured text. Used to tint the obvody results list so the
// legend's traffic light actually appears on the rows. The textual verdict is
// always rendered alongside — colour is an addition, never colour-only.
export const ROW_TINT: Record<CompositionColor, string> = {
  GREEN:  'bg-success-tint border-l-success',
  ORANGE: 'bg-warning-tint border-l-warning',
  RED:    'bg-danger-tint border-l-danger',
  NONE:   'bg-gray-50 border-l-gray-300',
}

export const ROW_TEXT: Record<CompositionColor, string> = {
  GREEN:  'text-success',
  ORANGE: 'text-warning',
  RED:    'text-danger',
  NONE:   'text-gray-600',
}

export function getRowTint(color: string | null | undefined): string {
  return ROW_TINT[(color as CompositionColor) ?? 'NONE'] ?? ROW_TINT.NONE
}

export function getRowText(color: string | null | undefined): string {
  return ROW_TEXT[(color as CompositionColor) ?? 'NONE'] ?? ROW_TEXT.NONE
}

export function getColorClass(color: string | null | undefined): string {
  return COLOR_CLASSES[(color as CompositionColor) ?? 'NONE'] ?? COLOR_CLASSES.NONE
}

export function getColorSymbol(color: string | null | undefined): string {
  return COLOR_SYMBOL[(color as CompositionColor) ?? 'NONE'] ?? '?'
}

export function getColorLabel(color: string | null | undefined): string {
  return COLOR_LABEL[(color as CompositionColor) ?? 'NONE'] ?? 'Nezhodnotené'
}

// Per-CONDITION verdict → semafor colour. Unlike composition_color (which is the
// district-wide roll-up), this maps a single condition's own `value` so each
// scorecard row shows ITS verdict, not the district's. PASS→GREEN, FAIL→RED,
// RISK→ORANGE, INCOMPLETE/INSUFFICIENT_DATA→NONE (the "?" not-yet-known marker).
// Values OUTSIDE the legal traffic light (SIGNAL, NOT_EVALUATED) are handled by
// isOutsideSemafor() below and must NOT be coloured red — see verdict-row.tsx.
export function valueToColor(value: string | null | undefined): CompositionColor {
  switch (value) {
    case 'PASS':
      return 'GREEN'
    case 'FAIL':
      return 'RED'
    case 'RISK':
      return 'ORANGE'
    default:
      // INCOMPLETE, INSUFFICIENT_DATA and anything unknown → not-yet-known.
      return 'NONE'
  }
}

// Values / conditions that sit OUTSIDE the § 44 legal traffic light and must
// never render a red ✕: soft SIGNAL/NO_SIGNAL indicators (sociálny kontext,
// demografia, jazyk) and NOT_EVALUATED. These get a neutral "mimo semaforu" dash
// instead of a colour symbol. Whether a whole CONDITION is outside the semafor
// (JAZYK / Pe / Pf) is decided by isSemaforApplicable() — a data-driven flag —
// not by hardcoding the condition code in the component.
export function isOutsideSemafor(value: string | null | undefined): boolean {
  return value === 'SIGNAL' || value === 'NO_SIGNAL' || value === 'NOT_EVALUATED'
}

// Condition-group membership: which §44 conditions feed the legal traffic light.
// S1–S3 (legal) and Pa–Pd (risk indicators) are IN the semafor; Pe/Pf (analytical
// signals) and JAZYK (podnet nad rámec § 44) are OUTSIDE it. This replaces the
// previous `condition_code === 'JAZYK'` hardcode in verdict-row.tsx (item 8a):
// outside-semafor status now comes from the condition-group contract, mirrored
// from the engine's LEGAL/INDICATOR/SIGNAL grouping in engine/compose.py.
const SEMAFOR_CONDITIONS = new Set(['S1', 'S2', 'S3', 'Pa', 'Pb', 'Pc', 'Pd'])

export function isSemaforApplicable(conditionCode: string | null | undefined): boolean {
  return conditionCode != null && SEMAFOR_CONDITIONS.has(conditionCode)
}

// Friendly SK label for a raw verdict value in the scorecard badge, so JAZYK /
// signal rows never expose the raw enum (e.g. "NO_SIGNAL", "NOT_EVALUATED") to a
// lay reader. PASS/FAIL/RISK keep their familiar enum (they map to the semafor).
export const VALUE_LABEL_SK: Record<string, string> = {
  PASS: 'PASS',
  FAIL: 'FAIL',
  RISK: 'RISK',
  INCOMPLETE: 'NEÚPLNÉ',
  INSUFFICIENT_DATA: 'MÁLO DÁT',
  SIGNAL: 'SIGNÁL',
  NO_SIGNAL: 'Bez podnetu',
  NOT_EVALUATED: 'Nevyhodnotené',
  ILUSTR_NO_DATA: 'Ilustračné — bez dát',
  ILUSTRATIVE_AVAILABLE: 'Ilustračné — dostupné',
}

export function getValueLabel(value: string | null | undefined): string {
  if (!value) return '—'
  return VALUE_LABEL_SK[value] ?? value
}
