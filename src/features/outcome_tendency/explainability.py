"""Explainability utilities for outcome tendency analysis."""

from __future__ import annotations

from collections import Counter

from src.database.models import Case
from src.features.outcome_tendency.schemas import ExplainabilitySignal, KeyFactor


class OutcomeExplainabilityEngine:
    """Builds lightweight explainability signals from cohort characteristics."""

    def build_signals(
        self,
        cases: list[Case],
        key_factors: list[KeyFactor],
        profile: str,
    ) -> list[ExplainabilitySignal]:
        """Return factor influence signals with evidence notes."""
        if not cases:
            return [
                ExplainabilitySignal(
                    factor=factor.name,
                    influence_percent=factor.influence_percent,
                    evidence_note="Derived from baseline heuristic profile due to sparse cohort.",
                )
                for factor in key_factors
            ]

        total = len(cases)
        court_counts = Counter((item.court or "Unknown").strip() for item in cases)
        top_court, top_court_count = court_counts.most_common(1)[0]

        section_count = sum(len(item.sections_invoked or []) for item in cases)
        avg_sections = section_count / max(1, total)
        sentence_coverage = sum(
            1 for item in cases if (item.sentence or "").strip()
        ) / max(1, total)

        evidence_templates = [
            f"Top forum concentration: {top_court} ({(top_court_count / total) * 100:.1f}% of cohort).",
            f"Average sections invoked per case: {avg_sections:.2f}.",
            f"Sentence detail present in {sentence_coverage * 100:.1f}% of cohort records.",
            f"Profile alignment used: {profile}.",
        ]

        signals: list[ExplainabilitySignal] = []
        for idx, factor in enumerate(key_factors):
            signals.append(
                ExplainabilitySignal(
                    factor=factor.name,
                    influence_percent=factor.influence_percent,
                    evidence_note=evidence_templates[idx % len(evidence_templates)],
                )
            )
        return signals
