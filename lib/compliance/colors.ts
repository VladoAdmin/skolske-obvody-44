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
