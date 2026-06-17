"""Scoring utilities for courtroom rubric evaluation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.features.courtroom.schemas import (
    CourtroomCriteriaScores,
    CourtroomEvaluationItem,
)


CRITERIA_WEIGHTS = {
    "legal_accuracy": 0.25,
    "constitutional_alignment": 0.20,
    "logical_coherence": 0.20,
    "precedent_usage": 0.15,
    "fairness_balance": 0.10,
    "practical_applicability": 0.10,
}


def weighted_score(criteria: CourtroomCriteriaScores) -> float:
    """Compute weighted rubric score using fixed criteria weights."""
    return round(
        (criteria.legal_accuracy * CRITERIA_WEIGHTS["legal_accuracy"])
        + (
            criteria.constitutional_alignment
            * CRITERIA_WEIGHTS["constitutional_alignment"]
        )
        + (criteria.logical_coherence * CRITERIA_WEIGHTS["logical_coherence"])
        + (criteria.precedent_usage * CRITERIA_WEIGHTS["precedent_usage"])
        + (criteria.fairness_balance * CRITERIA_WEIGHTS["fairness_balance"])
        + (
            criteria.practical_applicability
            * CRITERIA_WEIGHTS["practical_applicability"]
        ),
        2,
    )


def score_matrix(
    items: list[CourtroomEvaluationItem],
) -> dict[str, dict[str, float]]:
    """Build evaluator->target weighted score matrix."""
    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    for item in items:
        matrix[item.evaluator_role][item.target_role] = item.weighted_score
    return {k: dict(v) for k, v in matrix.items()}


def criteria_averages(items: list[CourtroomEvaluationItem]) -> dict[str, float]:
    """Compute average score per criterion across all evaluations."""
    if not items:
        return {
            "legal_accuracy": 0.0,
            "constitutional_alignment": 0.0,
            "logical_coherence": 0.0,
            "precedent_usage": 0.0,
            "fairness_balance": 0.0,
            "practical_applicability": 0.0,
        }

    totals = defaultdict(float)
    for item in items:
        c = item.criteria_scores
        totals["legal_accuracy"] += c.legal_accuracy
        totals["constitutional_alignment"] += c.constitutional_alignment
        totals["logical_coherence"] += c.logical_coherence
        totals["precedent_usage"] += c.precedent_usage
        totals["fairness_balance"] += c.fairness_balance
        totals["practical_applicability"] += c.practical_applicability

    count = len(items)
    return {k: round(v / count, 2) for k, v in totals.items()}


def consensus_and_disagreement(
    items: list[CourtroomEvaluationItem],
) -> tuple[float, float]:
    """Estimate consensus and disagreement from weighted score spread."""
    if not items:
        return 0.0, 1.0
    scores = [item.weighted_score for item in items]
    spread = max(scores) - min(scores)
    consensus = max(0.0, min(1.0, (100.0 - spread) / 100.0))
    disagreement = max(0.0, min(1.0, spread / 100.0))
    return round(consensus, 3), round(disagreement, 3)


def average_weighted_score(items: list[CourtroomEvaluationItem]) -> float:
    """Return average weighted score across evaluation items."""
    if not items:
        return 0.0
    return round(sum(item.weighted_score for item in items) / len(items), 2)


def evaluator_summary(items: list[CourtroomEvaluationItem]) -> dict[str, Any]:
    """Return evaluator-level summary stats used by transparency layer."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in items:
        grouped[item.evaluator_role].append(item.weighted_score)
    return {
        role: {
            "avg_weighted_score_given": round(sum(scores) / len(scores), 2)
            if scores
            else 0.0,
            "evaluations_count": len(scores),
        }
        for role, scores in grouped.items()
    }
