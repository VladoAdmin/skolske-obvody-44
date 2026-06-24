/**
 * Attribute validators — Sprint 0 stubs.
 * Validates required fields, types, date freshness, and reference integrity.
 * Used by ingestion (Sprint 1) and admin import (Sprint 5).
 */

import type {
  AttributeValidationInput,
  ValidationResult,
  ValidationIssue,
} from "./types";

/**
 * Check that all required fields are present and non-null.
 */
export function validateRequiredAttributes(
  input: AttributeValidationInput
): ValidationResult {
  const issues: ValidationIssue[] = [];

  for (const field of input.requiredFields) {
    const value = input.record[field];
    if (value === null || value === undefined || value === "") {
      issues.push({
        field,
        message: `Povinné pole '${field}' chýba alebo je prázdne`,
        severity: "error",
      });
    }
  }

  return { valid: issues.length === 0, issues };
}

/**
 * Stub: validate dataset freshness (data age vs. configured max staleness).
 * Sprint 1: wire to actual `source_date` field + configurable threshold.
 */
export function validateDataFreshness(
  _record: Record<string, unknown>,
  _maxAgeDays: number
): ValidationResult {
  // TODO Sprint 1: compare record.source_date against today
  return {
    valid: true,
    issues: [
      {
        message: "Freshness check nie je implementovaný (stub Sprint 0)",
        severity: "info",
      },
    ],
  };
}

/**
 * Stub: validate school type (druh školy) and language (vyuc_jazyk) fields.
 * Required for Š2 and Š3 compliance checks.
 */
export function validateSchoolAttributes(
  record: Record<string, unknown>
): ValidationResult {
  const VALID_SCHOOL_TYPES = ["ZS", "MS", "ZUS"]; // základná, materská, ZUŠ
  const VALID_LANGUAGES = ["SK", "HU", "RU"]; // slovenský, maďarský, rusínsky

  const issues: ValidationIssue[] = [];

  const druh = record["druh"] as string | undefined;
  const jazyk = record["vyuc_jazyk"] as string | undefined;

  if (druh && !VALID_SCHOOL_TYPES.includes(druh)) {
    issues.push({
      field: "druh",
      message: `Neznámy druh školy: '${druh}'. Povolené: ${VALID_SCHOOL_TYPES.join(", ")}`,
      severity: "warning",
    });
  }
  if (jazyk && !VALID_LANGUAGES.includes(jazyk)) {
    issues.push({
      field: "vyuc_jazyk",
      message: `Neznámy vyučovací jazyk: '${jazyk}'. Povolené: ${VALID_LANGUAGES.join(", ")}`,
      severity: "warning",
    });
  }

  return { valid: issues.filter((i) => i.severity === "error").length === 0, issues };
}
