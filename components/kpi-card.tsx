interface KpiCardProps {
  label: string
  value: string | number | null | undefined
  description?: string
}

export function KpiCard({ label, value, description }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums">{value ?? '—'}</dd>
      {description && (
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  )
}
