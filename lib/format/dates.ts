// Relative time formatting (no external deps)

export function relativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'práve teraz'
  if (diffMin < 60) return `pred ${diffMin} min`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `pred ${diffH} h`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 30) return `pred ${diffD} d`
  return date.toLocaleDateString('sk-SK', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return date.toLocaleDateString('sk-SK', { day: 'numeric', month: 'long', year: 'numeric' })
}
