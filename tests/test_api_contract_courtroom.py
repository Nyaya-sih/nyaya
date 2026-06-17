"""API contract tests for Phase 4 courtroom routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_courtroom_service
from src.features.courtroom.router import router
from src.features.courtroom.service import CourtroomService


def _build_client() -> tuple[TestClient, CourtroomService]:
    app = FastAPI()
    app.include_router(router)
    service = CourtroomService()
    app.dependency_overrides[get_courtroom_service] = lambda: service
    return TestClient(app), service


def test_create_analysis_contract_quick_mode():
    """Create analysis should return core lifecycle fields."""
    client, _ = _build_client()
    payload = {
        "mode": "quick",
        "source_type": "text",
        "case_text": "Sample criminal facts and legal context for courtroom simulation."
        * 5,
    }

    response = client.post("/api/v1/courtroom/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"].startswith("crt_")
    assert body["mode"] == "quick"
    assert body["status"] in {"completed", "degraded"}
    assert "created_at" in body
    assert "eta_seconds" in body


def test_get_analysis_and_status_contract():
    """Status and full report endpoints should return deterministic schema."""
    client, _ = _build_client()
    create = client.post(
        "/api/v1/courtroom/analyze",
        json={
            "mode": "full",
            "include_rebuttal": True,
            "source_type": "text",
            "case_text": "Constitutional criminal dispute facts." * 10,
        },
    )
    assert create.status_code == 200
    analysis_id = create.json()["analysis_id"]

    status = client.get(f"/api/v1/courtroom/analysis/{analysis_id}/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["analysis_id"] == analysis_id
    assert "progress_percent" in status_body
    assert "stage" in status_body

    full = client.get(f"/api/v1/courtroom/analysis/{analysis_id}")
    assert full.status_code == 200
    full_body = full.json()
    assert full_body["analysis_id"] == analysis_id
    assert "role_analyses" in full_body
    assert "evaluation_breakdown" in full_body
    assert "synthesis" in full_body
    assert "transparency_dashboard" in full_body
    assert "score_matrix" in full_body["transparency_dashboard"]
    assert "criteria_averages" in full_body["transparency_dashboard"]
    assert "evaluator_summary" in full_body["transparency_dashboard"]
    assert "legal_principles_applied" in full_body["synthesis"]
    assert "decision support workflow" in full_body["disclaimer"].lower()


def test_cancel_terminal_run_returns_not_cancelled():
    """Cancelling a completed run should be a no-op with cancelled=false."""
    client, _ = _build_client()
    create = client.post(
        "/api/v1/courtroom/analyze",
        json={"mode": "quick", "source_type": "text", "case_text": "facts" * 60},
    )
    analysis_id = create.json()["analysis_id"]

    cancel = client.post(f"/api/v1/courtroom/analysis/{analysis_id}/cancel")
    assert cancel.status_code == 200
    body = cancel.json()
    assert body["analysis_id"] == analysis_id
    assert body["cancelled"] is False
    assert body["status"] in {"completed", "degraded", "cancelled"}


def test_unknown_analysis_returns_404():
    """Unknown analysis id should return 404 on read endpoints."""
    client, _ = _build_client()
    missing = "crt_missing"

    res1 = client.get(f"/api/v1/courtroom/analysis/{missing}")
    assert res1.status_code == 404

    res2 = client.get(f"/api/v1/courtroom/analysis/{missing}/status")
    assert res2.status_code == 404

    res3 = client.post(f"/api/v1/courtroom/analysis/{missing}/cancel")
    assert res3.status_code == 404
