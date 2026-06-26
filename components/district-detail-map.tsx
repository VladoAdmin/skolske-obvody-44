// SSR-safe wrapper for the district detail map
import dynamic from 'next/dynamic'
import type {
  DistrictMapFeature,
  SoSchoolMarker,
  SoMrkOverlay,
  SoHousePoint,
  SoStreetGeocode,
  SoDistrictVoronoi,
  SoDistrictIsland,
} from '@/lib/supabase/types'
import { Skeleton } from '@/components/ui/skeleton'

interface DistrictDetailMapProps {
  currentDistrictId: string
  features: DistrictMapFeature[]
  voronoiFeatures: SoDistrictVoronoi[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  housePoints: SoHousePoint[]
  streetGeocodes: SoStreetGeocode[]
  islands: SoDistrictIsland[]
}

const DistrictDetailMapDynamic = dynamic(
  () => import('./district-detail-map.client').then((m) => m.DistrictDetailMapClient),
  {
    ssr: false,
    loading: () => <Skeleton className="w-full h-full rounded-none" />,
  }
)

export function DistrictDetailMap(props: DistrictDetailMapProps) {
  return (
    <div
      className="rounded-lg border border-border overflow-hidden w-full"
      style={{ height: 'clamp(350px, 50vw, 520px)' }}
    >
      <DistrictDetailMapDynamic {...props} />
    </div>
  )
}
