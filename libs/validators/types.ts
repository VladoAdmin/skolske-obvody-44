/**
 * Shared validator types — Sprint 0 scaffold.
 * Used by: ingestion pipeline (Sprint 1) + admin import (Sprint 5).
 * Singleton: do NOT duplicate these types in individual services.
 */

/** EPSG codes used in this project */
export type SupportedSRID = 4326 | 5514;

export type ValidationSeverity = "error" | "warning" | "info";

export interface ValidationIssue {
  field?: string;
  message: string;
  severity: ValidationSeverity;
  /** Row index or feature ID if applicable */
  ref?: string | number;
}

export interface ValidationResult {
  valid: boolean;
  issues: ValidationIssue[];
}

/** Geometry types expected in the district dataset */
export type DistrictGeometryType = "Polygon" | "MultiPolygon";

export interface GeometryValidationInput {
  /** GeoJSON geometry object (type + coordinates) */
  geometry: unknown;
  /** Expected SRID — reject if mismatch */
  expectedSrid: SupportedSRID;
}

export interface AttributeValidationInput {
  /** Row/feature as a plain record */
  record: Record<string, unknown>;
  /** Required top-level fields */
  requiredFields: string[];
}
