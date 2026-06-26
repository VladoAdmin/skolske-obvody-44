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

export function getColorClass(color: string | null | undefined): string {
  return COLOR_CLASSES[(color as CompositionColor) ?? 'NONE'] ?? COLOR_CLASSES.NONE
}

export function getColorSymbol(color: string | null | undefined): string {
  return COLOR_SYMBOL[(color as CompositionColor) ?? 'NONE'] ?? '?'
}

export function getColorLabel(color: string | null | undefined): string {
  return COLOR_LABEL[(color as CompositionColor) ?? 'NONE'] ?? 'Nezhodnotené'
}
