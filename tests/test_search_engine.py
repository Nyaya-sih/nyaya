"""Tests for SimilarCaseSearchEngine."""

import numpy as np

from src.config.settings import settings
from src.features.similar_cases.search_engine import SimilarCaseSearchEngine, SearchFilters
from src.features.similar_cases.similarity_analyzer import SimilarityExplanation, SimilarityDimension
from src.features.similar_cases.vector_store import SearchResult


class DummyEmbeddingGenerator:
    """Dummy embedding generator."""

    def generate_query_embedding(self, query_text: str) -> np.ndarray:
        return np.zeros(3072)


class DummyVectorStore:
    """Dummy vector store."""

    COLLECTION_COMBINED = "combined"
    COLLECTION_FACTUAL = "factual"
    COLLECTION_LEGAL = "legal"

    def __init__(self):
        self.last_params = None

    def search(self, **kwargs):
        self.last_params = kwargs
        return []


class DummySimilarityAnalyzer:
    """Dummy similarity analyzer."""

    def compute_rule_based_similarity(self, query_payload, candidate_payload, vector_score):
        return SimilarityExplanation(
            overall_score=0.5,
            dimensions=[SimilarityDimension(name="Statutory", score=0.5, reason="")],
            common_statutes=[],
            common_case_type=False,
            common_court=False,
            verdict_match=False,
            short_explanation="",
            detailed_explanation="",
        )


def _build_engine() -> SimilarCaseSearchEngine:
    engine = SimilarCaseSearchEngine.__new__(SimilarCaseSearchEngine)
    engine.embedding_generator = DummyEmbeddingGenerator()
    engine.vector_store = DummyVectorStore()
    engine.reranker = None
    engine.similarity_analyzer = DummySimilarityAnalyzer()
    return engine


def test_extract_query_metadata_criminal():
    """Keywords -> Criminal case_type."""
    engine = _build_engine()
    metadata = engine._extract_query_metadata("The accused sought bail after FIR")
    assert metadata["case_type"] == "Criminal"


def test_extract_query_metadata_writ():
    """Keywords -> Writ case_type."""
    engine = _build_engine()
    metadata = engine._extract_query_metadata("Writ petition under Article 226")
    assert metadata["case_type"] == "Writ"


def test_extract_query_metadata_statutes():
    """IPC detected in text."""
    engine = _build_engine()
    metadata = engine._extract_query_metadata("Offense under IPC Section 302")
    assert "IPC" in metadata["statutes_cited"]


def test_search_returns_empty_on_no_candidates(monkeypatch):
    """No vector results -> empty response."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    response = engine.search("query text", filters=SearchFilters(), top_k=5)
    assert response.total_results == 0


def test_search_includes_disclaimer(monkeypatch):
    """Response always has disclaimer."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    response = engine.search("query text", filters=SearchFilters(), top_k=5)
    assert response.disclaimer


def test_search_filters_passed_correctly(monkeypatch):
    """Filters reach vector store."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    filters = SearchFilters(court="Delhi High Court", case_type="Criminal", year_from=2020, year_to=2024)
    engine.search("query text", filters=filters, top_k=5)
    assert engine.vector_store.last_params["court_filter"] == "Delhi High Court"
