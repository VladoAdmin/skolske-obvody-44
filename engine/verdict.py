"""
Verdict dataclass — the 5-tuple {value, confidence, data_completeness, provenance, methodology}.

All checkers return a Verdict. runner.py collects them and writes to DB.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from engine.constants import ENGINE_VERSION, METHODOLOGY_VERSION, DATASET_VERSION


# Inline demo notices the UI must NOT show (the single top page banner is the
# only demo notice — item 7). The is_mock flag still carries the demo status
# internally; only the human-facing inline tags are stripped from evidence_text.
#
# IMPORTANT: enumerate the EXACT demo phrases that actually occur in checker
# evidence_text (grep engine/c_*.py). A broad `Ukážková?\s+[^.]*\.?` pattern is
# unsafe: against "Ukážková topologická vrstva — reálna geometria Prešova
# prekryvy nemá." it eats the whole legitimate sentence up to the first period.
# Match only the known fixed notices, longest-first so the S2 phrase wins before
# the generic "Ukážkové dáta." alternative.
_DEMO_TAG_RE = re.compile(
    r"\s*\[DEMO[^\]]*\]"                                           # [DEMO], [DEMO adresa], [DEMO inklúzia], [DEMO dáta], ...
    r"|\s*Ukážková topologická vrstva — reálna geometria Prešova prekryvy nemá\.?"  # c_s2 FAIL
    r"|\s*Ukážkové dáta\.?",                                       # the common trailing notice
    re.IGNORECASE,
)


def strip_demo_tags(text: str) -> str:
    """Remove scattered inline [DEMO]/Ukážkové-dáta notices from evidence text."""
    if not text:
        return text
    cleaned = _DEMO_TAG_RE.sub("", text)
    # Collapse any double spaces left behind, tidy spacing before punctuation.
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    return cleaned.strip()


@dataclass
class Verdict:
    district_id: str
    condition_code: str
    value: str                        # V.*
    confidence: float                 # 0.0 – 1.0
    data_completeness: float          # 0.0 – 1.0
    provenance: dict                  # {source, fetched_at, notes, ...}
    methodology: dict                 # {rule, threshold, version, ...}
    evidence_text: str = ""
    evidence_refs: list = field(default_factory=list)
    is_illustrative: bool = False
    is_proxy: bool = False
    is_mock: bool = False
    dataset_version: str = DATASET_VERSION
    methodology_version: str = METHODOLOGY_VERSION
    engine_version: str = ENGINE_VERSION

    def to_db_record(self) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "district_id": self.district_id,
            "condition_code": self.condition_code,
            "value": self.value,
            "confidence": round(self.confidence, 3),
            "data_completeness": round(self.data_completeness, 3),
            "provenance": json.dumps(self.provenance, ensure_ascii=False, default=str),
            "methodology": json.dumps(self.methodology, ensure_ascii=False, default=str),
            "is_illustrative": self.is_illustrative,
            "is_proxy": self.is_proxy,
            "is_mock": self.is_mock,
            "dataset_version": self.dataset_version,
            "methodology_version": self.methodology_version,
            "engine_version": self.engine_version,
            "evidence_text": strip_demo_tags(self.evidence_text),
            "evidence_refs": json.dumps(self.evidence_refs, ensure_ascii=False),
        }
