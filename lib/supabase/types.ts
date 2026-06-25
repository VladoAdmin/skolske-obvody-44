// Manual types for skolske_obvody views — generated types from views are flaky

export interface SoDistrictComposition {
  district_id: string
  composition_color: 'RED' | 'ORANGE' | 'GREEN' | 'NONE'
  composition_reason: string | null
  composition_details: Record<string, boolean> | null
  engine_version: string | null
  methodology_version: string | null
  computed_at: string | null
}

export interface SoDistrictMapFeature {
  id: string
  name: string
  municipality_id: string
  school_id: string | null
  geometry_confidence: string | null
  composition_color: 'RED' | 'ORANGE' | 'GREEN' | 'NONE'
  composition_reason: string | null
  geom_geojson: Record<string, unknown> | null
  school_geom_geojson: Record<string, unknown> | null
  school_name: string | null
}

export interface SoDistrictScorecardRow {
  district_id: string
  district_name: string
  municipality_id: string
  municipality_name: string | null
  vzn_id: string | null
  vzn_ref_url: string | null
  condition_code: string
  condition_label_sk: string
  condition_order: number
  value: string
  confidence: number | null
  data_completeness: number | null
  methodology_rule: string | null
  methodology_version: string | null
  provenance_source: string | null
  provenance_fetched_at: string | null
  evidence_public_text: string | null
  is_illustrative: boolean
  is_proxy: boolean
  is_mock: boolean
  composition_color: 'RED' | 'ORANGE' | 'GREEN' | 'NONE' | null
  computed_at: string | null
}

export interface SoMunicipalitySummary {
  municipality_id: string
  name: string
  districts_count: number
  schools_count: number
  open_findings_count: number
  red_districts_count: number
  orange_districts_count: number
  green_districts_count: number
  none_districts_count: number
}

export interface SoFindingPublic {
  finding_id: string
  district_id: string
  district_name: string
  municipality_id: string
  municipality_name: string | null
  condition_code: string
  condition_label_sk: string
  severity: string
  severity_rank: number
  status: string
  evidence_public_text: string | null
  provenance_source: string | null
  created_at: string
}

export interface SoEngineMetadata {
  dataset_version: string | null
  methodology_version: string | null
  engine_version: string | null
  last_engine_run_at: string | null
  verdicts_count: number
  districts_count: number
  schools_count: number
  open_findings_count: number
}

export interface SoSchoolMarker {
  id: string
  name: string
  kind: string | null
  geom_geojson: Record<string, unknown> | null
}

export interface SoMrkOverlay {
  id: string
  name: string | null
  severity_class: string | null
  geom_geojson: Record<string, unknown> | null
}

export interface SoFindingsPanelItem {
  finding_id: string
  district_id: string
  district_name: string
  municipality_id: string
  municipality_name: string | null
  condition_code: string
  condition_label_sk: string
  severity: string
  severity_rank: number
  status: string
  evidence_public_text: string | null
  provenance_source: string | null
  created_at: string
  district_geom_centroid_lon: number | null
  district_geom_centroid_lat: number | null
}

export interface SoDistrictOverlap {
  district_a_id: string
  district_a_name: string
  district_b_id: string
  district_b_name: string
  overlap_geojson: Record<string, unknown> | null
  overlap_area_m2: number
}

// Backward-compat aliases (deprecated — use So* names)
export type DistrictComposition = SoDistrictComposition
export type DistrictMapFeature = SoDistrictMapFeature
export type DistrictScorecardRow = SoDistrictScorecardRow
export type MunicipalitySummary = SoMunicipalitySummary
export type FindingPublic = SoFindingPublic
export type EngineMetadata = SoEngineMetadata
