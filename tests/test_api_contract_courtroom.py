"""API contract tests for Phase 4 courtroom routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import time
from threading import BoundedSemaphore, Event

from src.api.dependencies import get_courtroom_service
from src.features.courtroom.router import router
from src.features.courtroom.service import CourtroomService


def _build_client() -> tuple[TestClient, CourtroomService]:
    app = FastAPI()
    app.include_router(router)
    service = CourtroomService()
    app.state.courtroom_service = service
    app.dependency_overrides[get_courtroom_service] = lambda: service
    return TestClient(app), service


def _wait_terminal(client, analysis_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        report = client.get(f"/api/v1/courtroom/analysis/{analysis_id}").json()
        if report["status"] not in {"queued", "running"}:
            return report
        time.sleep(0.01)
    raise AssertionError("Courtroom workflow did not finish")


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
    assert body["status"] == "queued"
    assert "created_at" in body
    assert "eta_seconds" in body
    _wait_terminal(client, body["analysis_id"])


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
    _wait_terminal(client, analysis_id)

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
    assert "trial_events" in full_body
    assert len(full_body["trial_events"]) >= 3
    assert full_body["trial_events"][0]["stage"] == "ingestion"
    assert full_body["trial_events"][-1]["event_type"] == "vote"
    assert full_body["judge_review"]["approved"] is False
    assert full_body["initial_role_analyses"]
    assert full_body["rebuttal_enabled"] is True
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
    _wait_terminal(client, analysis_id)

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


def test_analysis_events_endpoint_replays_persisted_events():
    """Events endpoint should return persisted trial events and websocket replay."""
    client, _ = _build_client()
    create = client.post(
        "/api/v1/courtroom/analyze",
        json={"mode": "quick", "source_type": "text", "case_text": "facts" * 60},
    )
    analysis_id = create.json()["analysis_id"]
    _wait_terminal(client, analysis_id)

    events = client.get(f"/api/v1/courtroom/analysis/{analysis_id}/events")
    assert events.status_code == 200
    body = events.json()
    assert len(body) >= 3
    assert body[0]["stage"] == "ingestion"
    assert body[-1]["event_type"] == "vote"

    with client.websocket_connect(f"/api/v1/courtroom/analysis/{analysis_id}/events") as ws:
        payload = ws.receive_json()
        assert payload["stage"] == "ingestion"
        assert payload["event_type"] == "frame"


def test_websocket_delivers_new_position_before_run_finishes():
    client, service = _build_client()
    run = service.store.create_run("quick", True, "text", "test record")

    def publish(kind, content):
        return service._record_trial_event(
            analysis_id=run.analysis_id, stage="group_deliberation",
            role="Defense Counsel", agent_id="defense_counsel",
            model_provider="openai", model_id="test-model", round_number=1,
            event_type=kind, content=content, citations=[], confidence=0.5,
        )

    publish("frame", "Review started")
    with client.websocket_connect(f"/api/v1/courtroom/analysis/{run.analysis_id}/events") as ws:
        assert ws.receive_json()["content"] == "Review started"
        position = publish("position", "A live independent opinion")
        delivered = ws.receive_json()
        assert delivered["event_id"] == position.event_id
        assert delivered["event_type"] == "position"
        assert service.get_status(run.analysis_id).status == "queued"
        assert service.get_analysis(run.analysis_id).synthesis is None
        service.cancel_analysis(run.analysis_id)


def test_post_returns_before_worker_and_report_is_nullable(monkeypatch):
    client, service = _build_client()
    started, release, finished = Event(), Event(), Event()

    def blocked(run, *args):
        started.set()
        try:
            assert release.wait(5)
        finally:
            service._capacity.release()
            finished.set()

    monkeypatch.setattr(service, "_run_background", blocked)
    try:
        response = client.post("/api/v1/courtroom/analyze", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert started.wait(2)
        analysis_id = response.json()["analysis_id"]
        report = client.get(f"/api/v1/courtroom/analysis/{analysis_id}").json()
        assert report["synthesis"] is None
        assert report["judge_review"] is None
        assert report["transparency_dashboard"] is None
        assert report["initial_role_analyses"] == []
        assert client.post(f"/api/v1/courtroom/analysis/{analysis_id}/cancel").json()["cancelled"]
    finally:
        release.set()
    assert finished.wait(2)


def test_full_queue_returns_503(monkeypatch):
    client, service = _build_client()
    capacity = BoundedSemaphore(1)
    capacity.acquire()
    monkeypatch.setattr(service, "_capacity", capacity)
    assert client.post("/api/v1/courtroom/analyze", json={}).status_code == 503


def test_document_route_is_mounted_once_at_full_prefix():
    client, _ = _build_client()
    response = client.post(
        "/api/v1/courtroom/document", files={"file": ("facts.txt", b"Case facts", "text/plain")},
    )
    assert response.status_code == 200
    assert client.post("/api/v1/courtroom/api/v1/courtroom/document").status_code == 404
