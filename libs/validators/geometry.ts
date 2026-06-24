/**
 * Geometry validators — Sprint 0 stubs.
 *
 * These stubs define the contracts used by both ingestion (Sprint 1) and admin
 * import (Sprint 5). Actual PostGIS / Turf.js implementations go into Sprint 1.
 *
 * Contract:
 *   - Each function returns a ValidationResult; never throws.
 *   - Callers MUST check `result.valid` before proceeding.
 *   - Invalid geometry MUST NOT be inserted into the DB (ingestion gate).
 */

import type {
  GeometryValidationInput,
  ValidationResult,
  DistrictGeometryType,
} from "./types";

/** Accepted geometry types for school district polygons */
const ACCEPTED_DISTRICT_TYPES: DistrictGeometryType[] = [
  "Polygon",
  "MultiPolygon",
];

/**
 * Stub: validate that a GeoJSON geometry has an accepted type.
 * Sprint 1: replace body with real ST_IsValid-equivalent check via Turf.js
 * or defer to PostGIS after insert (ST_IsValid in migration constraint).
 */
export function validateGeometryType(
  input: GeometryValidationInput
): ValidationResult {
  // TODO Sprint 1: implement real geometry validation
  const geom = input.geometry as { type?: unknown } | null;
  if (!geom || typeof geom !== "object") {
    return {
      valid: false,
      issues: [
        { message: "Geometria chýba alebo nie je objekt", severity: "error" },
      ],
    };
  }
  if (!ACCEPTED_DISTRICT_TYPES.includes(geom.type as DistrictGeometryType)) {
    return {
      valid: false,
      issues: [
        {
          message: `Nepodporovaný typ geometrie: ${String(geom.type)}. Očakávaný: Polygon alebo MultiPolygon`,
          severity: "error",
        },
      ],
    };
  }
  return { valid: true, issues: [] };
}

/**
 * Stub: validate SRID consistency.
 * Sprint 1: wire to actual CRS detection (GeoJSON implies 4326; Shapefile may be 5514).
 */
export function validateSrid(
  input: GeometryValidationInput
): ValidationResult {
  // TODO Sprint 1: detect actual SRID from the source file/header and compare
  void input; // stub: suppress unused warning
  return {
    valid: true,
    issues: [
      {
        message: "SRID validácia nie je implementovaná (stub Sprint 0)",
        severity: "info",
      },
    ],
  };
}

/**
 * Stub: check for self-intersections (ST_IsValid equivalent).
 * Sprint 1: implement via Turf.js kinks() or PostGIS ST_IsValid.
 */
export function validateNoSelfIntersection(
  input: GeometryValidationInput
): ValidationResult {
  // TODO Sprint 1: use @turf/kinks or call ST_IsValid via Supabase RPC
  void input;
  return {
    valid: true,
    issues: [
      {
        message:
          "Self-intersection check nie je implementovaný (stub Sprint 0)",
        severity: "info",
      },
    ],
  };
}

/**
 * Stub: detect overlaps between two polygons of the same type+language.
 * Š2 compliance rule depends on this.
 * Sprint 1: implement via @turf/intersect or PostGIS ST_Overlaps.
 */
export function validateNoOverlap(
  _geomA: GeometryValidationInput,
  _geomB: GeometryValidationInput
): ValidationResult {
  // TODO Sprint 1: implement
  return {
    valid: true,
    issues: [
      {
        message: "Overlap check nie je implementovaný (stub Sprint 0)",
        severity: "info",
      },
    ],
  };
}
