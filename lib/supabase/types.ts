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

/** VLA-15: structured evidence trail of a street-level verdict — how the
 * engine arrived at it (VZN citation, register state, geometry, conclusion). */
export interface SoEvidenceTrail {
  vzn_citation: string | null
  register_state: string | null
  geometry_evidence: string | null
  conclusion_sk: string | null
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
  source_public: string | null
  method_public: string | null
  evidence_trail: SoEvidenceTrail | null
  created_at: string
  is_demo: boolean
  tag: string | null
}

export interface SoFindingExplanation {
  condition_code: string
  value: string
  explanation_sk: string
  model: string | null
  generated_at: string
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
  // true = verejná škola (zriaďovateľ mesto Prešov); false = súkromná/cirkevná
  is_public: boolean | null
}

export interface SoMrkOverlay {
  id: string
  name: string | null
  severity_class: string | null
  geom_geojson: Record<string, unknown> | null
}

// Locality-level MRK points (mrk_buildings) inside Prešov city districts —
// powers the "MRK lokality" map layer (item 14) instead of the whole-obec
// mrk_atlas polygon. geom_geojson is a Point.
// VLA-16: geographic_district_* is the real district whose polygon actually
// contains the point (ST_Within, same predicate engine/c_pe.py uses);
// assigned_district_* is the district the locality is administratively
// assigned to. When they differ, the locality is excluded into a different
// (and — per assigned/geographic_distance_m — typically more distant)
// school district than its geography would suggest.
export interface SoMrkLocality {
  id: string
  obec_name: string | null
  geom_geojson: Record<string, unknown> | null
  is_demo: boolean
  geographic_district_id: string | null
  geographic_district_name: string | null
  geographic_distance_m: number | null
  assigned_district_id: string | null
  assigned_district_name: string | null
  assigned_school_geojson: Record<string, unknown> | null
  assigned_distance_m: number | null
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
  source_public: string | null
  method_public: string | null
  evidence_trail: SoEvidenceTrail | null
  created_at: string
  is_demo: boolean
  tag: string | null
  district_geom_centroid_lon: number | null
  district_geom_centroid_lat: number | null
}

export interface SoDistrictOverlap {
  overlap_id: string | null
  district_a_id: string
  district_a_name: string
  district_b_id: string
  district_b_name: string
  overlap_geojson: Record<string, unknown> | null
  overlap_area_m2: number
  severity: string | null
  tag: string | null
  is_demo: boolean
}

export interface SoPskMunicipality {
  id: string
  name: string
  slug: string | null
  geom_geojson: Record<string, unknown> | null
  schools_count: number
  districts_count: number
}

export interface SoDistrictGeocodedGeom {
  id: string
  name: string
  geom_geojson: Record<string, unknown> | null
  geom_google_metadata: {
    ok_points?: number
    partial_match_points?: number
    built_at?: string
  } | null
}

export interface SoDistrictVoronoi {
  id: string
  name: string
  geom_voronoi_geojson: Record<string, unknown> | null
  geom_voronoi_metadata: {
    method?: string
    cell_count?: number
    created_at?: string
  } | null
}

export interface SoDistrictCleanGeom {
  id: string
  name: string
  school_id: string | null
  geom_clean_geojson: Record<string, unknown> | null
  geom_clean_metadata: {
    method?: 'clean_polygon' | 'voronoi_fallback'
    demo?: boolean
    note?: string
  } | null
}

export interface SoHouseDot {
  district_id: string
  street: string
  house_number: string
  lat: number
  lon: number
  is_demo: boolean
}

export interface SoStreetGeocode {
  district_id: string
  street: string
  lat: number
  lon: number
  status: string
  partial_match: boolean | null
  formatted_address: string | null
  point_geojson: Record<string, unknown> | null
}

// STREETS PIVOT: each district drawn as its VZN-assigned streets (coloured per
// school). One row per drawn segment — linestring_geojson is a LineString for an
// OSM-matched street, a Point for the ~5% fallback streets with no OSM line.
export interface SoDistrictStreetLine {
  district_id: string
  school_id: string | null
  street: string
  is_fallback_point: boolean
  linestring_geojson: Record<string, unknown> | null
  segment_id: string
}

// VLA-14: streets the VZN does not cover, classified BY THE ENGINE
// (engine/coverage_gaps.py):
//   'vzn_gap'  — in the address register but assigned by no VZN (Š1-family
//                structural finding, § 44 ods. 1)
// VLA-20: the former 'data_gap' ("nedostatočné dáta") category was removed
// from the product — the engine no longer emits it.
export interface SoStreetCoverageGap {
  street: string
  category: 'vzn_gap'
  in_register: boolean
  in_vzn: boolean
  register_address_count: number
  has_osm_line: boolean
  reason_sk: string
  is_demo: boolean
  geom_geojson: Record<string, unknown> | null
}

// VLA-20: barrier INPUT rows (public.so_barriers). Real barrier data is not
// available — the table is seeded with a FICTIONAL railway (is_demo=TRUE),
// so the map must always badge demo rows as DEMO.
export interface SoBarrier {
  kind: 'railway' | 'road'
  name: string
  is_demo: boolean
  reason_sk: string | null
  geom_geojson: Record<string, unknown> | null
}

export interface SoDistrictAddressStats {
  district_id: string
  habitable_addresses: number
  register_streets: number
  vzn_streets: number
  vzn_streets_in_register: number
  street_coverage: number
  // Step-2 CLEAN (authoritative) figures from register_adries_clean.
  clean_habitable_addresses: number
  clean_distinct_streets: number
  clean_street_coverage: number
  // Step-3 geometric-consistency signal: geocoded addresses the VZN assigns to
  // this district whose real coordinate falls outside its polygon (a place to
  // review, not a verdict change).
  mismatch_count: number
  computed_at: string | null
}

export interface SoHousePoint {
  district_id: string
  street: string
  house_number: string
  lat: number
  lon: number
  status: string
  partial_match: boolean | null
  formatted_address: string | null
  point_geojson: Record<string, unknown> | null
  valid: boolean | null
  validation_reason: string | null
  is_demo: boolean
}

export interface SoDistrictIsland {
  island_id: string
  district_id: string
  island_index: number
  area_m2: number | null
  street_count: number | null
  house_count: number | null
  streets: string[] | null
  house_numbers: string[] | null
  status: string | null
  anomaly_type: string | null
  severity: string | null
  tag: string | null
  is_demo: boolean
  geom_geojson: Record<string, unknown> | null
}

// Gap-filling DEMO values for non-binding indicators (P-a/P-c/P-d/P-f).
// Read ONLY by the scorecard UI for display. The verdict/composition path
// (district_compositions, district_scorecard) NEVER reads this — so mock
// values cannot affect the legal § 44 verdict. Always rendered with a DEMO
// badge + tooltip.
export interface SoMockIndicator {
  district_id: string
  condition_code: 'Pa' | 'Pc' | 'Pd' | 'Pf'
  display_value: string
  detail: Record<string, unknown> | null
  source_gap: string
  is_demo: boolean
}

// Backward-compat aliases (deprecated — use So* names)
export type DistrictComposition = SoDistrictComposition
export type DistrictMapFeature = SoDistrictMapFeature
export type DistrictScorecardRow = SoDistrictScorecardRow
export type MunicipalitySummary = SoMunicipalitySummary
export type FindingPublic = SoFindingPublic
export type EngineMetadata = SoEngineMetadata
