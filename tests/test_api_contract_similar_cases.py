"""API contract tests for similar-case retrieval routes."""

from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_search_engine
from src.features.similar_cases.router import router
from src.features.similar_cases.search_engine import SearchFilters
from src.features.similar_cases.similarity_analyzer import (
    SimilarityDimension,
    SimilarityExplanation,
)


@dataclass
class DummyResult:
    """Single dummy search result."""

    rank: int = 1
    case_id: int = 101
    case_title: str = "State vs Test"
    court: str = "High Court of Delhi"
    date_of_judgment: str = "2023-01-01"
    case_type: str = "Criminal"
    verdict: str = "Convicted"
    combined_score: float = 0.88
    vector_score: float = 0.82
    rerank_score: float = 0.92
    statutes_cited: Optional[list[str]] = None
    sections_invoked: Optional[list[str]] = None
    key_arguments_petitioner: str = ""
    key_arguments_respondent: str = ""
    court_reasoning: str = ""
    headnotes: Optional[list[str]] = None
    similarity_explanation: Optional[SimilarityExplanation] = None


@dataclass
class DummyResponse:
    """Dummy search response envelope."""

    query_summary: str
    total_results: int
    search_time_ms: float
    results: list
    filters_applied: dict
    disclaimer: str
    retrieval_mode: str = "full"
    warnings: Optional[list[str]] = None


class DummySearchEngine:
    """Minimal search engine stub for API contract tests."""

    def __init__(self):
        self.last_filters = None
        self.last_top_k = None

    def search(
        self, query_text: str, filters: SearchFilters, top_k: int, exclude_case_id=None
    ):
        self.last_filters = filters
        self.last_top_k = top_k
        explanation = SimilarityExplanation(
            overall_score=0.88,
            dimensions=[
                SimilarityDimension(name="Statutory", score=0.9, reason="Common IPC")
            ],
            common_statutes=["IPC"],
            common_case_type=True,
            common_court=True,
            verdict_match=True,
            short_explanation="Both involve IPC.",
            detailed_explanation="details",
        )
        result = DummyResult(
            statutes_cited=["IPC"],
            sections_invoked=["Section 302"],
            headnotes=[],
            similarity_explanation=explanation,
        )
        return DummyResponse(
            query_summary="query",
            total_results=1,
            search_time_ms=12.0,
            results=[result],
            filters_applied={"similarity_mode": filters.similarity_mode},
            disclaimer="decision support",
            retrieval_mode="full",
            warnings=[],
        )


def _build_client() -> tuple[TestClient, DummySearchEngine]:
    app = FastAPI()
    app.include_router(router)
    engine = DummySearchEngine()
    app.dependency_overrides[get_search_engine] = lambda: engine
    return TestClient(app), engine


def test_text_search_rejects_short_query():
    """Text payload shorter than 100 chars should fail validation."""
    client, _ = _build_client()
    payload = {"text": "too short", "top_k": 5, "similarity_mode": "combined"}
    response = client.post("/api/v1/cases/similar", json=payload)
    assert response.status_code == 422


def test_text_search_rejects_invalid_similarity_mode():
    """Similarity mode must be one of allowed literals."""
    client, _ = _build_client()
    payload = {
        "text": "a" * 120,
        "top_k": 5,
        "similarity_mode": "random",
    }
    response = client.post("/api/v1/cases/similar", json=payload)
    assert response.status_code == 422


def test_text_search_contract_shape_and_filter_mapping():
    """Successful search should return stable contract fields."""
    client, engine = _build_client()
    payload = {
        "text": "b" * 140,
        "top_k": 3,
        "court": "High Court of Delhi",
        "similarity_mode": "factual",
    }
    response = client.post("/api/v1/cases/similar", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert "query_summary" in body
    assert "results" in body
    assert "disclaimer" in body
    assert body["total_results"] == 1
    assert body["results"][0]["case_id"] == 101
    assert body["results"][0]["dimensions"][0]["name"] == "Statutory"
    assert body["retrieval_mode"] == "full"
    assert isinstance(body["warnings"], list)
    assert engine.last_filters is not None
    assert engine.last_filters.similarity_mode == "factual"
    assert engine.last_top_k == 3
