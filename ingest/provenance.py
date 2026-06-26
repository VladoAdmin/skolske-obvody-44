"""
Provenance helper — attaches source metadata to ingested records.

Every record must carry:
  source_name: str   (human-readable dataset name)
  source_date: date  (date data was originally published / last updated)
  geometry_quality: int 1–10  (per DATA_INVENTORY_PSK.csv q-ratings)

This module also builds the JSONB 'provenance' blob used in the
verdicts table (PRD §12 — each verdict cites its source chain).
"""

from datetime import date, datetime
from typing import Optional


def attach_provenance(
    record: dict,
    source_name: str,
    source_date: str,  # ISO date string
    geometry_quality: Optional[int] = None,
) -> dict:
    """
    Add provenance fields to a record dict in-place.
    Returns the record for chaining.
    """
    record["source_name"] = source_name
    record["source_date"] = source_date
    if geometry_quality is not None:
        record["geometry_quality"] = geometry_quality
    return record


def build_provenance_blob(
    source_name: str,
    source_url: str,
    fetched_at: Optional[str] = None,
    transformations: Optional[list[str]] = None,
) -> dict:
    """
    Build the JSONB provenance blob used in verdicts.provenance.
    Schema: {source, source_url, fetched_at, transformations[]}
    """
    return {
        "source": source_name,
        "source_url": source_url,
        "fetched_at": fetched_at or datetime.utcnow().isoformat() + "Z",
        "transformations": transformations or [],
    }


def build_methodology_blob(
    rule: str,
    version: str,
    threshold: Optional[dict] = None,
) -> dict:
    """Build the JSONB methodology blob used in verdicts.methodology."""
    blob = {
        "rule": rule,
        "version": version,
    }
    if threshold:
        blob["threshold"] = threshold
    return blob
