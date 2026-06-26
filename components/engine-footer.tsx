import { createPublicClient } from '@/lib/supabase/server'
import type { EngineMetadata } from '@/lib/supabase/types'
import { formatDate } from '@/lib/format/dates'

export async function EngineFooter() {
  let meta: EngineMetadata | null = null
  try {
    const sb = createPublicClient()
    const { data } = await sb
      .from('so_engine_metadata')
      .select('*')
      .maybeSingle()
    meta = data as EngineMetadata | null
  } catch {
    // ignore
  }

  return (
    <footer className="border-t border-border bg-muted/30 px-6 py-3 text-xs text-muted-foreground">
      <span>
        Engine: <code className="font-mono">{meta?.engine_version ?? 'n/a'}</code>
        {' · '}
        Metodika: <code className="font-mono">{meta?.methodology_version ?? 'n/a'}</code>
        {' · '}
        Posledný beh: <span>{formatDate(meta?.last_engine_run_at)}</span>
      </span>
    </footer>
  )
}
