// SSR-safe wrapper: dynamically imports the Leaflet client component
import dynamic from 'next/dynamic'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoDistrictIsland, SoPskMunicipality, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi, SoDistrictCleanGeom, SoHouseDot } from '@/lib/supabase/types'
import type { DistrictPopupSummary } from '@/lib/compliance/school-popup'
import { Skeleton } from '@/components/ui/skeleton'

interface RegionMapProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  findings: SoFindingsPanelItem[]
  overlaps?: SoDistrictOverlap[]
  islands?: SoDistrictIsland[]
  municipalities?: SoPskMunicipality[]
  streetGeocodes?: SoStreetGeocode[]
  housePoints?: SoHousePoint[]
  voronoiGeom?: SoDistrictVoronoi[]
  cleanGeom?: SoDistrictCleanGeom[]
  houseDots?: SoHouseDot[]
  districtSummaries?: Record<string, DistrictPopupSummary>
  initialMode?: 'sk' | 'psk'
}

const RegionMapDynamic = dynamic(
  () => import('./region-map.client').then((m) => m.RegionMapClient),
  {
    ssr: false,
    loading: () => <Skeleton className="w-full h-full rounded-none" />,
  }
)

export function RegionMap({ features, schools, mrkOverlays, findings, overlaps = [], islands = [], municipalities = [], streetGeocodes = [], housePoints = [], voronoiGeom = [], cleanGeom = [], houseDots = [], districtSummaries = {}, initialMode = 'sk' }: RegionMapProps) {
  return <RegionMapDynamic features={features} schools={schools} mrkOverlays={mrkOverlays} findings={findings} overlaps={overlaps} islands={islands} municipalities={municipalities} streetGeocodes={streetGeocodes} housePoints={housePoints} voronoiGeom={voronoiGeom} cleanGeom={cleanGeom} houseDots={houseDots} districtSummaries={districtSummaries} initialMode={initialMode} />
}
