// Server components — no client interactivity needed
import { cn } from '@/lib/utils'

interface ConditionCardProps {
  code: string
  title: string
  body: string
  type?: 'law' | 'indicator'
}

export function ConditionCard({ code, title, body, type = 'indicator' }: ConditionCardProps) {
  return (
    <div className={cn(
      'rounded-lg border p-4 space-y-1.5',
      type === 'law'
        ? 'border-red-200 bg-red-50/50'
        : 'border-border bg-muted/20'
    )}>
      <div className="flex items-center gap-2">
        <span className={cn(
          'inline-block rounded px-2 py-0.5 font-mono text-xs font-bold',
          type === 'law'
            ? 'bg-red-100 text-red-800'
            : 'bg-primary/10 text-primary'
        )}>
          {code}
        </span>
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed">{body}</p>
    </div>
  )
}

interface SemaforCardProps {
  color: 'green' | 'orange' | 'red' | 'gray'
  title: string
  body: string
}

const SEMAFOR_STYLES: Record<SemaforCardProps['color'], string> = {
  green:  'border-green-200 bg-green-50/50',
  orange: 'border-orange-200 bg-orange-50/50',
  red:    'border-red-200 bg-red-50/50',
  gray:   'border-gray-200 bg-gray-50/50',
}

export function SemaforCard({ color, title, body }: SemaforCardProps) {
  return (
    <div className={cn('rounded-lg border p-4 space-y-1.5', SEMAFOR_STYLES[color])}>
      <p className="text-sm font-semibold">{title}</p>
      <p className="text-xs text-muted-foreground leading-relaxed">{body}</p>
    </div>
  )
}
