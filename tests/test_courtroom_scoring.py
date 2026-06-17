"""Unit tests for courtroom scoring utilities."""

from src.features.courtroom.anonymizer import AnalysisAnonymizer
from src.features.courtroom.scoring import (
    average_weighted_score,
    consensus_and_disagreement,
    criteria_averages,
    score_matrix,
    weighted_score,
)
from src.features.courtroom.schemas import (
    CourtroomCriteriaScores,
    CourtroomEvaluationItem,
    CourtroomRoleAnalysis,
)


def test_weighted_score_uses_fixed_weights():
    """Weighted score should combine criteria using configured constants."""
    criteria = CourtroomCriteriaScores(
        legal_accuracy=80,
        constitutional_alignment=70,
        logical_coherence=75,
        precedent_usage=60,
        fairness_balance=65,
        practical_applicability=85,
    )
    score = weighted_score(criteria)
    assert score == 73.0


def test_matrix_and_aggregate_stats():
    """Matrix and aggregate helpers should return stable numeric summaries."""
    items = [
        CourtroomEvaluationItem(
            evaluator_role="Prosecution Counsel",
            target_role="Defense Counsel",
            criteria_scores=CourtroomCriteriaScores(
                legal_accuracy=76,
                constitutional_alignment=71,
                logical_coherence=74,
                precedent_usage=68,
                fairness_balance=70,
                practical_applicability=72,
            ),
            weighted_score=73.1,
            justification="A",
        ),
        CourtroomEvaluationItem(
            evaluator_role="Defense Counsel",
            target_role="Prosecution Counsel",
            criteria_scores=CourtroomCriteriaScores(
                legal_accuracy=72,
                constitutional_alignment=69,
                logical_coherence=71,
                precedent_usage=67,
                fairness_balance=68,
                practical_applicability=70,
            ),
            weighted_score=70.4,
            justification="B",
        ),
    ]

    matrix = score_matrix(items)
    assert matrix["Prosecution Counsel"]["Defense Counsel"] == 73.1
    assert matrix["Defense Counsel"]["Prosecution Counsel"] == 70.4

    crit = criteria_averages(items)
    assert crit["legal_accuracy"] == 74.0
    assert crit["precedent_usage"] == 67.5

    consensus, disagreement = consensus_and_disagreement(items)
    assert 0.0 <= consensus <= 1.0
    assert 0.0 <= disagreement <= 1.0

    avg = average_weighted_score(items)
    assert avg == 71.75


def test_anonymizer_roundtrip_mapping():
    """Anonymizer should produce deterministic role/anon mapping counts."""
    analyses = [
        CourtroomRoleAnalysis(
            role_name="Prosecution Counsel",
            analysis_text="P",
            citations=["S1"],
            confidence=0.7,
        ),
        CourtroomRoleAnalysis(
            role_name="Defense Counsel",
            analysis_text="D",
            citations=["S2"],
            confidence=0.6,
        ),
    ]
    anon, role_to_anon, anon_to_role = AnalysisAnonymizer().anonymize(analyses)
    assert len(anon) == 2
    assert role_to_anon["Prosecution Counsel"].startswith("ANON-")
    assert anon_to_role[role_to_anon["Defense Counsel"]] == "Defense Counsel"
