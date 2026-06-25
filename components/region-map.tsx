// SSR-safe wrapper: dynamically imports the Leaflet client component
import dynamic from 'next/dynamic'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoFindingsPanelItem, SoDistrictOverlap, SoPskMunicipality, SoDistrictGeocodedGeom, SoStreetGeocode, SoHousePoint, SoDistrictVoronoi } from '@/lib/supabase/types'
import { Skeleton } from '@/components/ui/skeleton'

interface RegionMapProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  findings: SoFindingsPanelItem[]
  overlaps?: SoDistrictOverlap[]
  municipalities?: SoPskMunicipality[]
  geocodedGeom?: SoDistrictGeocodedGeom[]
  streetGeocodes?: SoStreetGeocode[]
  housePoints?: SoHousePoint[]
  voronoiGeom?: SoDistrictVoronoi[]
  initialMode?: 'sk' | 'psk'
}

const RegionMapDynamic = dynamic(
  () => import('./region-map.client').then((m) => m.RegionMapClient),
  {
    ssr: false,
    loading: () => <Skeleton className="w-full h-full rounded-none" />,
  }
)

export function RegionMap({ features, schools, mrkOverlays, findings, overlaps = [], municipalities = [], geocodedGeom = [], streetGeocodes = [], housePoints = [], voronoiGeom = [], initialMode = 'sk' }: RegionMapProps) {
  return <RegionMapDynamic features={features} schools={schools} mrkOverlays={mrkOverlays} findings={findings} overlaps={overlaps} municipalities={municipalities} geocodedGeom={geocodedGeom} streetGeocodes={streetGeocodes} housePoints={housePoints} voronoiGeom={voronoiGeom} initialMode={initialMode} />
}
