'use client'

// SSR-safe wrapper: dynamically imports the Leaflet client component
import dynamic from 'next/dynamic'
import type { DistrictMapFeature, SoSchoolMarker, SoMrkOverlay, SoMrkLocality, SoPskMunicipality, SoHousePoint, SoHouseDot, SoDistrictStreetLine, SoFindingsPanelItem, SoStreetCoverageGap, SoBarrier, SoDistrictLongestRoute, SoSharedMunicipalityArea } from '@/lib/supabase/types'
import type { DistrictPopupSummary } from '@/lib/compliance/school-popup'
import { Skeleton } from '@/components/ui/skeleton'
import { useDemoMode } from '@/lib/demo-mode/context'

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
  const { demoMode } = useDemoMode()

  // VLA-34: real-only mode drops every is_demo=true row client-side, off the
  // already-fetched arrays — no refetch. RegionMapClient builds its Leaflet
  // layers imperatively once per `mode` change and caches them in a ref, so
  // simply passing new filtered arrays would NOT rebuild the already-mounted
  // layers (MRK/barriers/house points/findings legend). Forcing a remount via
  // `key` on toggle is the only way to make the map actually re-derive its
  // layers from the filtered data without invasively rewriting that effect's
  // caching.
  const visibleMrkLocalities = demoMode ? mrkLocalities : mrkLocalities.filter((l) => !l.is_demo)
  const visibleBarriers = demoMode ? barriers : barriers.filter((b) => !b.is_demo)
  const visibleHousePoints = demoMode ? housePoints : housePoints.filter((p) => !p.is_demo)
  const visibleCoverageGaps = demoMode ? coverageGaps : coverageGaps.filter((g) => !g.is_demo)
  const visibleFindings = demoMode ? findings : findings.filter((f) => !f.is_demo)

  return (
    <RegionMapDynamic
      key={demoMode ? 'demo' : 'real'}
      features={features}
      schools={schools}
      mrkOverlays={mrkOverlays}
      mrkLocalities={visibleMrkLocalities}
      municipalities={municipalities}
      streetLines={streetLines}
      housePoints={visibleHousePoints}
      houseDots={houseDots}
      coverageGaps={visibleCoverageGaps}
      barriers={visibleBarriers}
      longestRoutes={longestRoutes}
      sharedMunicipalityAreas={sharedMunicipalityAreas}
      findings={visibleFindings}
      districtSummaries={districtSummaries}
      initialMode={initialMode}
    />
  )
}
