"""Cohort selection utilities for outcome tendency analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import Case
from src.features.outcome_tendency.schemas import OutcomeTendencyRequest


@dataclass
class CohortSelectionResult:
    """Selected cohort and metadata used for tendency calculations."""

    cases: list[Case]
    profile: str
    filters_used: dict[str, str | int | None]


class OutcomeCohortSelector:
    """Selects comparable historical cohorts from stored cases."""

    def select(
        self,
        payload: OutcomeTendencyRequest,
        db_session: Session,
        profile_hint: str,
    ) -> CohortSelectionResult:
        """Return best-effort comparable cohort from DB."""
        profile = profile_hint
        query = db_session.query(Case).filter(Case.verdict.isnot(None))
        query = query.filter(Case.validation_status != "invalid")

        if payload.year_from is not None:
            query = query.filter(Case.date_of_judgment >= date(payload.year_from, 1, 1))
        if payload.year_to is not None:
            query = query.filter(Case.date_of_judgment <= date(payload.year_to, 12, 31))

        query = self._apply_profile_filter(query, profile)
        cases = (
            query.order_by(Case.date_of_judgment.desc().nullslast())
            .limit(payload.top_k_similar)
            .all()
        )

        # Relax case-type filter if too narrow.
        if len(cases) < 75:
            relaxed_query = db_session.query(Case).filter(Case.verdict.isnot(None))
            relaxed_query = relaxed_query.filter(Case.validation_status != "invalid")
            if payload.year_from is not None:
                relaxed_query = relaxed_query.filter(
                    Case.date_of_judgment >= date(payload.year_from, 1, 1)
                )
            if payload.year_to is not None:
                relaxed_query = relaxed_query.filter(
                    Case.date_of_judgment <= date(payload.year_to, 12, 31)
                )
            cases = (
                relaxed_query.order_by(Case.date_of_judgment.desc().nullslast())
                .limit(payload.top_k_similar)
                .all()
            )

        filters_used: dict[str, str | int | None] = {
            "source_type": payload.source_type,
            "mode": payload.mode,
            "year_from": payload.year_from,
            "year_to": payload.year_to,
            "top_k_similar": payload.top_k_similar,
            "profile": profile,
        }
        return CohortSelectionResult(
            cases=cases, profile=profile, filters_used=filters_used
        )

    def _apply_profile_filter(self, query, profile: str):
        profile_rules = {
            "criminal": ["criminal", "bail"],
            "economic": ["economic", "financial", "company", "tax"],
            "constitutional": ["constitutional", "writ", "fundamental rights"],
            "civil": ["civil", "contract", "property", "family"],
        }
        terms = profile_rules.get(profile, [])
        if not terms:
            return query

        like_filters = [Case.case_type.ilike(f"%{term}%") for term in terms]
        predicate = like_filters[0]
        for item in like_filters[1:]:
            predicate = predicate | item
        return query.filter(predicate)
