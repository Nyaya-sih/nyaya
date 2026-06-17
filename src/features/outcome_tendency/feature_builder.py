"""Feature extraction utilities for Phase 5 outcome tendency modeling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.database.models import Case


@dataclass
class FeatureDataset:
    """Tabular feature dataset for benchmark training."""

    rows: list[dict[str, Any]]
    targets: list[str]


class OutcomeFeatureBuilder:
    """Builds model-ready features from persisted case records."""

    def build(self, cases: list[Case]) -> FeatureDataset:
        """Extract row-wise features and target labels from cases."""
        rows: list[dict[str, Any]] = []
        targets: list[str] = []

        for item in cases:
            verdict = self._normalize_verdict(item.verdict or "")
            if verdict == "unknown":
                continue

            case_type = (item.case_type or "unknown").strip().lower()
            court = (item.court or "unknown").strip().lower()
            sections = item.sections_invoked or []
            charges = item.charges or []
            headnotes = item.headnotes or []

            text_signal = " ".join(
                part
                for part in [
                    item.case_title or "",
                    item.court_reasoning or "",
                    " ".join(headnotes),
                ]
                if part
            )

            rows.append(
                {
                    "case_type": case_type,
                    "court_level": self._court_level(court),
                    "court": court,
                    "year": item.date_of_judgment.year if item.date_of_judgment else 0,
                    "sections_count": len(sections),
                    "charges_count": len(charges),
                    "headnotes_count": len(headnotes),
                    "has_sentence": 1 if (item.sentence or "").strip() else 0,
                    "reasoning_len": len((item.court_reasoning or "").split()),
                    "text_len": len(text_signal.split()),
                    "validation_status": (item.validation_status or "unknown").lower(),
                }
            )
            targets.append(verdict)

        return FeatureDataset(rows=rows, targets=targets)

    def _court_level(self, court: str) -> str:
        value = court.lower()
        if "supreme" in value:
            return "supreme"
        if "high court" in value or "hc" in value:
            return "high"
        if "district" in value or "sessions" in value:
            return "district"
        return "other"

    def _normalize_verdict(self, verdict: str) -> str:
        value = verdict.strip().lower()
        if not value:
            return "unknown"
        if "convict" in value:
            return "convicted"
        if "acquit" in value:
            return "acquitted"
        if "dismiss" in value:
            return "dismissed"
        if "allow" in value:
            if "part" in value:
                return "partially_allowed"
            return "allowed"
        if "remand" in value:
            return "remanded"
        if "settle" in value:
            return "settled"
        return "other"
