import dynamic from 'next/dynamic'
import type { DistrictMapFeature } from '@/lib/supabase/types'
import { Skeleton } from '@/components/ui/skeleton'

interface DistrictMiniMapProps {
  feature: DistrictMapFeature | null
}

const DistrictMiniMapDynamic = dynamic(
  () => import('./district-mini-map.client').then((m) => m.DistrictMiniMapClient),
  {
    ssr: false,
    loading: () => <Skeleton className="w-full h-full rounded-none" />,
  }
)

export function DistrictMiniMap({ feature }: DistrictMiniMapProps) {
  return (
    <div className="rounded-lg border border-border overflow-hidden" style={{ height: 220 }}>
      <DistrictMiniMapDynamic feature={feature} />
    </div>
  )
}
