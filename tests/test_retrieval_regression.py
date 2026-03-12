"""Regression guardrails for retrieval output ordering."""

from typing import Any, cast

import numpy as np

from src.config.settings import settings
from src.features.similar_cases.search_engine import (
    SimilarCaseSearchEngine,
    SearchFilters,
)
from src.features.similar_cases.similarity_analyzer import (
    SimilarityExplanation,
    SimilarityDimension,
)
from src.features.similar_cases.vector_store import SearchResult


class DummyEmbeddingGenerator:
    """Dummy embedding generator for deterministic tests."""

    def generate_query_embedding(self, query_text: str) -> np.ndarray:
        return np.zeros(3072)


class DummyVectorStore:
    """Vector store with fixed snapshot candidates."""

    COLLECTION_COMBINED = "combined"
    COLLECTION_FACTUAL = "factual"
    COLLECTION_LEGAL = "legal"

    def search(self, **kwargs):
        return [
            SearchResult(
                case_id=501,
                case_title="A",
                court="High Court of Delhi",
                date_of_judgment="2023-01-01",
                case_type="Criminal",
                verdict="Convicted",
                similarity_score=0.91,
                payload={
                    "statutes_cited": ["IPC"],
                    "sections_invoked": ["Section 302"],
                },
            ),
            SearchResult(
                case_id=777,
                case_title="B",
                court="High Court of Delhi",
                date_of_judgment="2022-09-10",
                case_type="Criminal",
                verdict="Convicted",
                similarity_score=0.55,
                payload={
                    "statutes_cited": ["IPC"],
                    "sections_invoked": ["Section 302"],
                },
            ),
            SearchResult(
                case_id=888,
                case_title="C",
                court="High Court of Bombay",
                date_of_judgment="2018-03-04",
                case_type="Civil",
                verdict="Dismissed",
                similarity_score=0.40,
                payload={"statutes_cited": ["Companies Act"], "sections_invoked": []},
            ),
        ]


class DummySimilarityAnalyzer:
    """Deterministic explanation analyzer."""

    def compute_rule_based_similarity(
        self, query_payload, candidate_payload, vector_score
    ):
        return SimilarityExplanation(
            overall_score=vector_score,
            dimensions=[
                SimilarityDimension(
                    name="Statutory", score=vector_score, reason="snapshot"
                )
            ],
            common_statutes=list(candidate_payload.get("statutes_cited", [])),
            common_case_type=True,
            common_court=True,
            verdict_match=True,
            short_explanation="snapshot",
            detailed_explanation="snapshot",
        )


def _build_engine() -> SimilarCaseSearchEngine:
    engine = SimilarCaseSearchEngine.__new__(SimilarCaseSearchEngine)
    engine_any = cast(Any, engine)
    engine_any.embedding_generator = DummyEmbeddingGenerator()
    engine_any.vector_store = DummyVectorStore()
    engine_any.reranker = None
    engine_any.similarity_analyzer = DummySimilarityAnalyzer()
    return cast(SimilarCaseSearchEngine, engine_any)


def test_retrieval_snapshot_ids(monkeypatch):
    """Snapshot order should stay stable above similarity threshold."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    monkeypatch.setattr(settings, "similarity_threshold", 0.5)

    response = engine.search(
        "criminal section 302 ipc high court appeal text",
        filters=SearchFilters(),
        top_k=10,
    )
    snapshot_ids = [item.case_id for item in response.results]
    assert snapshot_ids == [501, 777]


def test_retrieval_disclaimer_contains_support_language(monkeypatch):
    """Regression guard for legal disclaimer wording."""
    engine = _build_engine()
    monkeypatch.setattr(settings, "enable_reranking", False)
    response = engine.search(
        "criminal section 302 ipc high court appeal text",
        filters=SearchFilters(),
        top_k=5,
    )
    assert "decision support tool" in response.disclaimer.lower()
