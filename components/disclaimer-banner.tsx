// Server wrapper: fetches engine metadata for version strings, then renders client banner
import { createPublicClient } from '@/lib/supabase/server'
import { DisclaimerBannerClient } from './disclaimer-banner.client'
import type { EngineMetadata } from '@/lib/supabase/types'

interface Props {
  alwaysShow?: boolean
}

export async function DisclaimerBanner({ alwaysShow = false }: Props) {
  let methodologyVersion = 'n/a'
  let engineVersion = 'n/a'

  try {
    const sb = createPublicClient()
    const { data } = await sb
      .from('engine_metadata')
      .select('methodology_version, engine_version')
      .maybeSingle()
    const meta = data as EngineMetadata | null
    methodologyVersion = meta?.methodology_version ?? 'n/a'
    engineVersion = meta?.engine_version ?? 'n/a'
  } catch {
    // Supabase not configured — show banner with fallback text
  }

  return (
    <DisclaimerBannerClient
      alwaysShow={alwaysShow}
      methodologyVersion={methodologyVersion}
      engineVersion={engineVersion}
    />
  )
}
