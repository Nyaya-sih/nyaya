"""Tests for rule-based similarity explanations."""

from src.features.similar_cases.similarity_analyzer import SimilarityAnalyzer


def test_common_statutes_are_normalized_for_overlap():
    """Statute/section overlap should be case/whitespace insensitive."""
    analyzer = SimilarityAnalyzer()
    explanation = analyzer.compute_rule_based_similarity(
        query_payload={
            "statutes_cited": ["ipc", " CrPC "],
            "sections_invoked": ["section 302"],
            "case_type": "Criminal",
            "court": "High Court of Delhi",
            "year": 2023,
        },
        candidate_payload={
            "statutes_cited": ["IPC"],
            "sections_invoked": ["SECTION 302"],
            "case_type": "Criminal",
            "court": "DELHI HIGH COURT",
            "year": 2022,
            "verdict": "Convicted",
        },
        vector_score=0.8,
    )

    assert "IPC" in explanation.common_statutes
    assert "SECTION 302" in explanation.common_statutes
    assert explanation.common_court is True


def test_short_explanation_does_not_claim_missing_overlap():
    """Explanation should avoid claiming overlap when there is none."""
    analyzer = SimilarityAnalyzer()
    explanation = analyzer.compute_rule_based_similarity(
        query_payload={
            "statutes_cited": ["IPC 302"],
            "case_type": "Criminal",
            "court": "High Court of Delhi",
            "year": 2023,
            "verdict": "Convicted",
        },
        candidate_payload={
            "statutes_cited": ["Companies Act"],
            "case_type": "Civil",
            "court": "High Court of Bombay",
            "year": 2012,
            "verdict": "Dismissed",
        },
        vector_score=0.4,
    )

    short = explanation.short_explanation.lower()
    assert "both involve" not in short
    assert "same court" not in short
