// SSR-safe wrapper: dynamically imports the Leaflet client component
import dynamic from 'next/dynamic'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoMrkLocality, SoPskMunicipality, SoHousePoint, SoHouseDot, SoDistrictStreetLine, SoFindingsPanelItem, SoStreetCoverageGap, SoBarrier } from '@/lib/supabase/types'
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

export function RegionMap({ features, schools, mrkOverlays, mrkLocalities = [], municipalities = [], streetLines = [], housePoints = [], houseDots = [], coverageGaps = [], barriers = [], findings = [], districtSummaries = {}, initialMode = 'sk' }: RegionMapProps) {
  return <RegionMapDynamic features={features} schools={schools} mrkOverlays={mrkOverlays} mrkLocalities={mrkLocalities} municipalities={municipalities} streetLines={streetLines} housePoints={housePoints} houseDots={houseDots} coverageGaps={coverageGaps} barriers={barriers} findings={findings} districtSummaries={districtSummaries} initialMode={initialMode} />
}
