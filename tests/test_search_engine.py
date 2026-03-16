"""Tests for SimilarCaseSearchEngine."""

from typing import Any, cast

import numpy as np

from src.config.settings import settings
from src.features.similar_cases.search_engine import (
    SimilarCaseSearchEngine,
    SearchFilters,
)
from src.features.similar_cases.reranker import RankedResult
from src.features.similar_cases.similarity_analyzer import (
    SimilarityExplanation,
    SimilarityDimension,
)
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
    COLLECTION_FULLTEXT = "fulltext"

    def __init__(self):
        self.last_params = None
        self.fulltext_exists = False
        self.next_results = []

    def search(self, **kwargs):
        self.last_params = kwargs
        return list(self.next_results)

    def collection_exists(self, name: str) -> bool:
        return self.fulltext_exists and name == self.COLLECTION_FULLTEXT


class DummySimilarityAnalyzer:
    """Dummy similarity analyzer."""

    def compute_rule_based_similarity(
        self, query_payload, candidate_payload, vector_score
    ):
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
    engine_any = cast(Any, engine)
    engine_any.embedding_generator = DummyEmbeddingGenerator()
    engine_any.vector_store = DummyVectorStore()
    engine_any.reranker = None
    engine_any.similarity_analyzer = DummySimilarityAnalyzer()
    return cast(SimilarCaseSearchEngine, engine_any)


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


def test_extract_query_metadata_civil_jurisdiction_keywords():
    """Civil jurisdiction phrases should map to Civil case type."""
    engine = _build_engine()
    metadata = engine._extract_query_metadata(
        "Ordinary Original Civil Jurisdiction in a title suit"
    )
    assert metadata["case_type"] == "Civil"


def test_extract_query_metadata_high_court_at_pattern():
    """Court parser should support 'High Court at <city>' format."""
    engine = _build_engine()
    metadata = engine._extract_query_metadata(
        "IN THE HIGH COURT AT CALCUTTA ORIGINAL SIDE"
    )
    assert metadata["court"] == "High Court of Calcutta"


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
    filters = SearchFilters(
        court="Delhi High Court", case_type="Criminal", year_from=2020, year_to=2024
    )
    engine.search("query text", filters=filters, top_k=5)
    store = cast(DummyVectorStore, engine.vector_store)
    assert store.last_params is not None
    assert store.last_params["court_filter"] == "Delhi High Court"


def test_search_mode_maps_to_factual_collection(monkeypatch):
    """Factual mode uses factual collection."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    monkeypatch.setattr(settings, "enable_fulltext_search", False)
    filters = SearchFilters(similarity_mode="factual")
    engine.search("criminal appeal before high court", filters=filters, top_k=5)
    store = cast(DummyVectorStore, engine.vector_store)
    assert store.last_params is not None
    assert store.last_params["collection"] == store.COLLECTION_FACTUAL


def test_search_mode_maps_to_legal_collection(monkeypatch):
    """Legal mode uses legal collection."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    monkeypatch.setattr(settings, "enable_fulltext_search", False)
    filters = SearchFilters(similarity_mode="legal")
    engine.search("section 302 ipc and crpc proceedings", filters=filters, top_k=5)
    store = cast(DummyVectorStore, engine.vector_store)
    assert store.last_params is not None
    assert store.last_params["collection"] == store.COLLECTION_LEGAL


def test_invalid_mode_falls_back_to_combined(monkeypatch):
    """Unknown mode should fallback to combined collection."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    monkeypatch.setattr(settings, "enable_fulltext_search", False)
    filters = SearchFilters(similarity_mode="unknown")
    engine.search("criminal appeal before high court", filters=filters, top_k=5)
    store = cast(DummyVectorStore, engine.vector_store)
    assert store.last_params is not None
    assert store.last_params["collection"] == store.COLLECTION_COMBINED


def test_combined_mode_prefers_fulltext_when_available(monkeypatch):
    """Combined mode should use fulltext collection if enabled and available."""
    engine = _build_engine()
    store = cast(DummyVectorStore, engine.vector_store)
    store.fulltext_exists = True
    monkeypatch.setattr(settings, "enable_reranking", False)
    monkeypatch.setattr(settings, "enable_fulltext_search", True)
    filters = SearchFilters(similarity_mode="combined")
    engine.search("criminal appeal before high court", filters=filters, top_k=5)
    assert store.last_params is not None
    assert store.last_params["collection"] == store.COLLECTION_FULLTEXT


def test_search_reports_degraded_mode_when_reranker_missing(monkeypatch):
    """Should flag degraded mode when reranking enabled but unavailable."""
    engine = _build_engine()
    store = cast(DummyVectorStore, engine.vector_store)
    store.next_results = [
        SearchResult(
            case_id=10,
            case_title="Case A",
            court="High Court of Delhi",
            date_of_judgment="2023-01-01",
            case_type="Criminal",
            verdict="Convicted",
            similarity_score=0.8,
            payload={"statutes_cited": ["IPC"], "sections_invoked": ["Section 302"]},
        )
    ]

    monkeypatch.setattr(settings, "enable_reranking", True)
    response = engine.search(
        "criminal appeal high court section 302 ipc text",
        filters=SearchFilters(),
        top_k=5,
    )
    assert response.retrieval_mode == "degraded"
    assert response.warnings
    assert response.total_results == 1


def test_search_falls_back_when_reranker_raises(monkeypatch):
    """Reranker errors should fallback to vector ranking and warn."""

    class ExplodingReranker:
        def rerank(self, query_text, candidates, top_k=10):
            raise RuntimeError("boom")

    engine = _build_engine()
    store = cast(DummyVectorStore, engine.vector_store)
    store.next_results = [
        SearchResult(
            case_id=11,
            case_title="Case B",
            court="High Court of Delhi",
            date_of_judgment="2023-01-02",
            case_type="Criminal",
            verdict="Convicted",
            similarity_score=0.77,
            payload={"statutes_cited": ["IPC"], "sections_invoked": ["Section 302"]},
        )
    ]
    cast(Any, engine).reranker = ExplodingReranker()

    monkeypatch.setattr(settings, "enable_reranking", True)
    response = engine.search(
        "criminal appeal high court section 302 ipc text",
        filters=SearchFilters(),
        top_k=5,
    )
    assert response.retrieval_mode == "degraded"
    assert any("Reranker" in warning for warning in response.warnings)
    assert response.total_results == 1


def test_reranker_receives_limited_candidate_pool(monkeypatch):
    """Reranker should only receive top-N candidates by vector score."""

    class CapturingReranker:
        def __init__(self):
            self.last_count = 0

        def rerank(self, query_text, candidates, top_k=10):
            self.last_count = len(candidates)
            return [
                RankedResult(
                    case_id=c.case_id,
                    case_title=c.case_title,
                    court=c.court,
                    date_of_judgment=c.date_of_judgment,
                    case_type=c.case_type,
                    verdict=c.verdict,
                    vector_score=c.similarity_score,
                    rerank_score=c.similarity_score,
                    combined_score=c.similarity_score,
                    payload=c.payload,
                )
                for c in candidates[:top_k]
            ]

    engine = _build_engine()
    store = cast(DummyVectorStore, engine.vector_store)
    store.next_results = [
        SearchResult(
            case_id=i,
            case_title=f"Case {i}",
            court="High Court of Delhi",
            date_of_judgment="2023-01-01",
            case_type="Criminal",
            verdict="Convicted",
            similarity_score=float(100 - i) / 100.0,
            payload={"statutes_cited": ["IPC"], "sections_invoked": ["Section 302"]},
        )
        for i in range(1, 31)
    ]
    reranker = CapturingReranker()
    cast(Any, engine).reranker = reranker

    monkeypatch.setattr(settings, "enable_reranking", True)
    monkeypatch.setattr(settings, "reranker_candidate_limit", 12)
    response = engine.search(
        "criminal appeal high court section 302 ipc text",
        filters=SearchFilters(),
        top_k=5,
    )
    assert reranker.last_count == 12
    assert response.total_results == 5
