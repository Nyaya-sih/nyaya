"""Tests for CrossEncoderReranker."""

import numpy as np

from src.features.similar_cases.reranker import CrossEncoderReranker


class DummyModel:
    """Dummy CrossEncoder model."""

    def predict(self, pairs):
        return [float(i) for i in range(len(pairs))]


class DummyCandidate:
    """Dummy candidate wrapper."""

    def __init__(self, score):
        self.case_id = 1
        self.case_title = "Title"
        self.court = "Court"
        self.date_of_judgment = "2024-01-01"
        self.case_type = "Criminal"
        self.verdict = "Convicted"
        self.similarity_score = score
        self.payload = {
            "case_title": "Title",
            "case_type": "Criminal",
            "key_arguments_petitioner": None,
            "court_reasoning": None,
            "verdict": "Convicted",
        }


def test_rerank_returns_ranked_results(monkeypatch):
    """Output is RankedResult list."""
    monkeypatch.setattr("src.features.similar_cases.reranker.CrossEncoder", lambda *_: DummyModel())
    reranker = CrossEncoderReranker()
    results = reranker.rerank("query", [DummyCandidate(0.9)], top_k=1)
    assert len(results) == 1


def test_rerank_sorted_by_combined_score(monkeypatch):
    """Results in descending order."""
    monkeypatch.setattr("src.features.similar_cases.reranker.CrossEncoder", lambda *_: DummyModel())
    reranker = CrossEncoderReranker()
    candidates = [DummyCandidate(0.1), DummyCandidate(0.9)]
    results = reranker.rerank("query", candidates, top_k=2)
    assert results[0].combined_score >= results[1].combined_score


def test_rerank_respects_top_k(monkeypatch):
    """Returns exactly top_k results."""
    monkeypatch.setattr("src.features.similar_cases.reranker.CrossEncoder", lambda *_: DummyModel())
    reranker = CrossEncoderReranker()
    candidates = [DummyCandidate(0.1), DummyCandidate(0.2), DummyCandidate(0.3)]
    results = reranker.rerank("query", candidates, top_k=2)
    assert len(results) == 2


def test_build_candidate_text_handles_none(monkeypatch):
    """None payload fields -> no crash."""
    monkeypatch.setattr("src.features.similar_cases.reranker.CrossEncoder", lambda *_: DummyModel())
    reranker = CrossEncoderReranker()
    candidate_text = reranker._build_candidate_text({"case_title": None})
    assert isinstance(candidate_text, str)


def test_scores_normalized_0_to_1(monkeypatch):
    """All normalized scores in [0, 1]."""
    monkeypatch.setattr("src.features.similar_cases.reranker.CrossEncoder", lambda *_: DummyModel())
    reranker = CrossEncoderReranker()
    candidates = [DummyCandidate(0.1), DummyCandidate(0.2)]
    results = reranker.rerank("query", candidates, top_k=2)
    for result in results:
        assert 0.0 <= result.rerank_score <= 1.0
