// Severity → badge variant + non-color symbol

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export const SEVERITY_CLASSES: Record<Severity, string> = {
  critical: 'bg-red-100 text-red-800 border-red-300',
  high:     'bg-orange-100 text-orange-800 border-orange-300',
  medium:   'bg-yellow-100 text-yellow-800 border-yellow-300',
  low:      'bg-blue-100 text-blue-800 border-blue-300',
  info:     'bg-gray-100 text-gray-600 border-gray-300',
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Kritická',
  high:     'Vysoká',
  medium:   'Stredná',
  low:      'Nízka',
  info:     'Informácia',
}

export const SEVERITY_RANK: Record<Severity, number> = {
  critical: 5,
  high:     4,
  medium:   3,
  low:      2,
  info:     1,
}

export function getSeverityClass(severity: string | null | undefined): string {
  return SEVERITY_CLASSES[(severity as Severity) ?? 'info'] ?? SEVERITY_CLASSES.info
}

export function getSeverityLabel(severity: string | null | undefined): string {
  return SEVERITY_LABEL[(severity as Severity) ?? 'info'] ?? severity ?? 'info'
}
