// SSR-safe wrapper: dynamically imports the Leaflet client component
import dynamic from 'next/dynamic'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoMrkLocality, SoPskMunicipality, SoHousePoint, SoHouseDot, SoDistrictStreetLine, SoFindingsPanelItem, SoStreetCoverageGap, SoBarrier, SoDistrictLongestRoute, SoSharedMunicipalityArea } from '@/lib/supabase/types'
import type { DistrictPopupSummary } from '@/lib/compliance/school-popup'
import { Skeleton } from '@/components/ui/skeleton'

interface RegionMapProps {
  features: DistrictMapFeature[]
  schools: SoSchoolMarker[]
  mrkOverlays: SoMrkOverlay[]
  mrkLocalities?: SoMrkLocality[]
  municipalities?: SoPskMunicipality[]
  streetLines?: SoDistrictStreetLine[]
  housePoints?: SoHousePoint[]
  houseDots?: SoHouseDot[]
  // VLA-14 engine-classified uncovered streets
  coverageGaps?: SoStreetCoverageGap[]
  // VLA-20 barrier input rows (fictional demo railway → DEMO badge)
  barriers?: SoBarrier[]
  // VLA-17: 5 longest real walking routes per district (comparison only)
  longestRoutes?: SoDistrictLongestRoute[]
  // VLA-21: shared-municipality catchment areas (VZN grades 5-9 / 1-9)
  sharedMunicipalityAreas?: SoSharedMunicipalityArea[]
  findings?: SoFindingsPanelItem[]
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

export function RegionMap({ features, schools, mrkOverlays, mrkLocalities = [], municipalities = [], streetLines = [], housePoints = [], houseDots = [], coverageGaps = [], barriers = [], longestRoutes = [], sharedMunicipalityAreas = [], findings = [], districtSummaries = {}, initialMode = 'sk' }: RegionMapProps) {
  return <RegionMapDynamic features={features} schools={schools} mrkOverlays={mrkOverlays} mrkLocalities={mrkLocalities} municipalities={municipalities} streetLines={streetLines} housePoints={housePoints} houseDots={houseDots} coverageGaps={coverageGaps} barriers={barriers} longestRoutes={longestRoutes} sharedMunicipalityAreas={sharedMunicipalityAreas} findings={findings} districtSummaries={districtSummaries} initialMode={initialMode} />
}
