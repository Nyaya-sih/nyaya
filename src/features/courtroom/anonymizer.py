"""Anonymization helpers for courtroom peer evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.courtroom.schemas import CourtroomRoleAnalysis


@dataclass
class AnonymousAnalysis:
    """An anonymized role analysis payload."""

    anonymous_id: str
    role_name: str
    analysis_text: str
    citations: list[str]
    confidence: float


class AnalysisAnonymizer:
    """Create anonymous analysis IDs and reversible mappings."""

    def anonymize(
        self, role_analyses: list[CourtroomRoleAnalysis]
    ) -> tuple[list[AnonymousAnalysis], dict[str, str], dict[str, str]]:
        """Return anonymized analyses with role<->anon mappings."""
        anon_items: list[AnonymousAnalysis] = []
        role_to_anon: dict[str, str] = {}
        anon_to_role: dict[str, str] = {}

        for idx, item in enumerate(role_analyses, start=1):
            anon_id = f"ANON-{idx}"
            role_to_anon[item.role_name] = anon_id
            anon_to_role[anon_id] = item.role_name
            anon_items.append(
                AnonymousAnalysis(
                    anonymous_id=anon_id,
                    role_name=item.role_name,
                    analysis_text=item.analysis_text,
                    citations=item.citations,
                    confidence=item.confidence,
                )
            )

        return anon_items, role_to_anon, anon_to_role
