"""API contract tests for similar-case retrieval routes."""

from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_db_session
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
        self.last_exclude_case_id = None

    def search(
        self,
        query_text: str,
        filters: SearchFilters,
        top_k: int,
        exclude_case_id=None,
        **_kwargs,
    ):
        self.last_filters = filters
        self.last_top_k = top_k
        self.last_exclude_case_id = exclude_case_id
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

    class DummyCase:
        id = 999
        case_title = "State vs Test"
        court = "High Court of Delhi"
        headnotes = ["Bail jurisprudence", "Section 302 analysis"]
        key_arguments_petitioner = "Petitioner argument text " * 10
        key_arguments_respondent = "Respondent argument text " * 10
        court_reasoning = "Reasoning text " * 10
        sections_invoked = ["Section 302 IPC", "Section 34 IPC"]
        full_text = "Full judgment text " * 30
        case_type = "Criminal"
        verdict = "Convicted"

        class _Date:
            year = 2023

        date_of_judgment = _Date()

    class DummyQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return DummyCase()

    class DummySession:
        def query(self, *_args, **_kwargs):
            return DummyQuery()

    app.dependency_overrides[get_search_engine] = lambda: engine
    app.dependency_overrides[get_db_session] = lambda: DummySession()
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


def test_get_similar_to_case_applies_case_context_filters():
    """Case-to-case endpoint should prefill case metadata filters."""
    client, engine = _build_client()
    response = client.get("/api/v1/cases/999/similar", params={"top_k": 4})

    assert response.status_code == 200
    assert engine.last_filters is not None
    assert engine.last_filters.court == "High Court of Delhi"
    assert engine.last_filters.case_type == "Criminal"
    assert engine.last_filters.verdict == "Convicted"
    assert engine.last_filters.year_from == 2008
    assert engine.last_filters.year_to == 2024
    assert engine.last_exclude_case_id == 999
    assert engine.last_top_k == 4


def test_get_similar_to_case_uses_progressive_filter_fallback():
    """If strict filters return empty, endpoint should retry with relaxed filters."""

    class FallbackEngine(DummySearchEngine):
        def __init__(self):
            super().__init__()
            self.calls = []

        def search(
            self,
            query_text: str,
            filters: SearchFilters,
            top_k: int,
            exclude_case_id=None,
            **kwargs,
        ):
            self.calls.append(filters)
            if len(self.calls) <= 3:
                return DummyResponse(
                    query_summary="query",
                    total_results=0,
                    search_time_ms=10.0,
                    results=[],
                    filters_applied={"similarity_mode": filters.similarity_mode},
                    disclaimer="decision support",
                    retrieval_mode="full",
                    warnings=[],
                )
            return super().search(
                query_text,
                filters,
                top_k,
                exclude_case_id,
                **kwargs,
            )

    app = FastAPI()
    app.include_router(router)
    engine = FallbackEngine()

    class DummyCase:
        id = 999
        case_title = "State vs Test"
        court = "High Court of Delhi"
        headnotes = ["Bail jurisprudence", "Section 302 analysis"]
        key_arguments_petitioner = "Petitioner argument text " * 10
        key_arguments_respondent = "Respondent argument text " * 10
        court_reasoning = "Reasoning text " * 10
        sections_invoked = ["Section 302 IPC", "Section 34 IPC"]
        full_text = "Full judgment text " * 30
        case_type = "Criminal"
        verdict = "Convicted"

        class _Date:
            year = 2023

        date_of_judgment = _Date()

    class DummyQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return DummyCase()

    class DummySession:
        def query(self, *_args, **_kwargs):
            return DummyQuery()

    app.dependency_overrides[get_search_engine] = lambda: engine
    app.dependency_overrides[get_db_session] = lambda: DummySession()
    client = TestClient(app)

    response = client.get("/api/v1/cases/999/similar", params={"top_k": 4})
    assert response.status_code == 200
    assert len(engine.calls) == 4
    assert engine.calls[0].verdict == "Convicted"
    assert engine.calls[1].verdict is None
    assert engine.calls[2].court is None
    assert engine.calls[2].case_type == "Criminal"
    assert engine.calls[3].case_type is None
    assert engine.calls[3].year_from is None


def test_get_similar_to_case_falls_back_from_fulltext_to_combined_mode():
    """Fulltext mode should retry in combined mode when fulltext returns empty."""

    class ModeFallbackEngine(DummySearchEngine):
        def __init__(self):
            super().__init__()
            self.calls = []

        def search(
            self,
            query_text: str,
            filters: SearchFilters,
            top_k: int,
            exclude_case_id=None,
            **kwargs,
        ):
            self.calls.append(filters)
            if len(self.calls) <= 4:
                return DummyResponse(
                    query_summary="query",
                    total_results=0,
                    search_time_ms=10.0,
                    results=[],
                    filters_applied={"similarity_mode": filters.similarity_mode},
                    disclaimer="decision support",
                    retrieval_mode="full",
                    warnings=[],
                )
            return super().search(
                query_text,
                filters,
                top_k,
                exclude_case_id,
                **kwargs,
            )

    app = FastAPI()
    app.include_router(router)
    engine = ModeFallbackEngine()

    class DummyCase:
        id = 999
        case_title = "State vs Test"
        court = "High Court of Delhi"
        headnotes = ["Bail jurisprudence", "Section 302 analysis"]
        key_arguments_petitioner = "Petitioner argument text " * 10
        key_arguments_respondent = "Respondent argument text " * 10
        court_reasoning = "Reasoning text " * 10
        sections_invoked = ["Section 302 IPC", "Section 34 IPC"]
        full_text = "Full judgment text " * 30
        case_type = "Criminal"
        verdict = "Convicted"

        class _Date:
            year = 2023

        date_of_judgment = _Date()

    class DummyQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return DummyCase()

    class DummySession:
        def query(self, *_args, **_kwargs):
            return DummyQuery()

    app.dependency_overrides[get_search_engine] = lambda: engine
    app.dependency_overrides[get_db_session] = lambda: DummySession()
    client = TestClient(app)

    response = client.get(
        "/api/v1/cases/999/similar",
        params={"top_k": 4, "similarity_mode": "fulltext"},
    )
    assert response.status_code == 200
    assert len(engine.calls) == 5
    assert engine.calls[0].similarity_mode == "fulltext"
    assert engine.calls[3].similarity_mode == "fulltext"
    assert engine.calls[4].similarity_mode == "combined"
