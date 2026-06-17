"""API contract tests for Phase 5 outcome tendency route."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_db_session, get_outcome_tendency_service
from src.features.outcome_tendency.router import router
from src.features.outcome_tendency.service import OutcomeTendencyService


def _build_client() -> tuple[TestClient, OutcomeTendencyService]:
    app = FastAPI()
    app.include_router(router)
    service = OutcomeTendencyService()

    class DummyQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

    class DummySession:
        def query(self, *_args, **_kwargs):
            return DummyQuery()

    app.dependency_overrides[get_outcome_tendency_service] = lambda: service
    app.dependency_overrides[get_db_session] = lambda: DummySession()
    return TestClient(app), service


def test_tendency_from_text_contract():
    """Text input should return deterministic tendency contract fields."""
    client, _ = _build_client()
    payload = {
        "mode": "baseline",
        "source_type": "text",
        "case_text": (
            "Accused seeks bail in a criminal matter; prosecution alleges flight risk "
            "and witness intimidation while defense contests evidence quality. "
        )
        * 3,
    }

    response = client.post("/api/v1/cases/tendency", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"].startswith("tend_")
    assert body["status"] in {"completed", "insufficient_data"}
    assert body["sample_size"] > 0
    assert len(body["outcome_distribution"]) >= 2
    assert len(body["trend_analysis"]) >= 1
    assert len(body["key_factors"]) >= 1
    assert "method" in body["confidence_band"]
    assert "reliability_score" in body["confidence_band"]
    assert len(body["confidence_notes"]) >= 1
    assert "explainability_signals" in body
    assert "bias_audit" in body
    assert "disparity_flag" in body["bias_audit"]
    assert "historical pattern analysis" in body["disclaimer"].lower()
    assert "not a verdict prediction" in body["disclaimer"].lower()


def test_tendency_from_case_id_contract():
    """Case-id source should return complete payload with confidence and limits."""
    client, _ = _build_client()
    response = client.post(
        "/api/v1/cases/tendency",
        json={
            "mode": "ml",
            "source_type": "case_id",
            "case_id": 42,
            "top_k_similar": 450,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cohort_filters"]["source_type"] == "case_id"
    assert body["cohort_filters"]["mode"] == "ml"
    assert "confidence_band" in body
    assert "limitations" in body


def test_tendency_invalid_input_returns_400():
    """Missing required source content should return 400."""
    client, _ = _build_client()
    response = client.post(
        "/api/v1/cases/tendency",
        json={
            "source_type": "text",
            "case_text": "too short",
        },
    )
    assert response.status_code == 400
