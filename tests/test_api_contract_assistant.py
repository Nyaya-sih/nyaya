"""API contract tests for Phase 3 legal assistant routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_db_session, get_legal_assistant_service
from src.features.legal_assistant.router import router
from src.features.legal_assistant.service import LegalAssistantService


def _build_client() -> tuple[TestClient, LegalAssistantService]:
    app = FastAPI()
    app.include_router(router)
    service = LegalAssistantService()

    class DummyCase:
        id = 42
        case_title = "State vs Placeholder"
        headnotes = ["Bail", "Section 302"]
        key_arguments_petitioner = "Petitioner arguments"
        key_arguments_respondent = "Respondent arguments"
        court_reasoning = "Court reasoning text"
        full_text = "Full text " * 100

    class DummyQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return DummyCase()

    class DummySession:
        def query(self, *_args, **_kwargs):
            return DummyQuery()

    app.dependency_overrides[get_legal_assistant_service] = lambda: service
    app.dependency_overrides[get_db_session] = lambda: DummySession()
    return TestClient(app), service


def test_create_session_contract():
    """Session creation should return required fields."""
    client, _ = _build_client()
    response = client.post("/api/v1/assistant/session")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"].startswith("asst_")
    assert "created_at" in body
    assert "expires_at" in body
    assert body["ttl_minutes"] > 0


def test_query_requires_existing_session():
    """Query on unknown session should return 404."""
    client, _ = _build_client()
    payload = {
        "session_id": "asst_missing_session",
        "question": "What are the key weaknesses in the prosecution case?",
    }
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 404


def test_query_returns_contract_and_disclaimer():
    """Query response should include answer, confidence, citations and disclaimer."""
    client, _ = _build_client()
    session = client.post("/api/v1/assistant/session").json()
    session_id = session["session_id"]

    upload_content = (
        "This is a sample legal context document discussing Section 302 IPC and "
        "grounds for bail in criminal appeals. "
    ) * 8
    files = {
        "file": (
            "context.txt",
            upload_content.encode("utf-8"),
            "text/plain",
        )
    }
    set_context_response = client.post(
        f"/api/v1/assistant/session/{session_id}/context/upload",
        files=files,
    )
    assert set_context_response.status_code == 200

    payload = {
        "session_id": session_id,
        "question": "Analyze the likely statutory issues and applicable sections.",
        "top_k": 5,
    }
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert "answer_text" in body
    assert "confidence" in body
    assert "disclaimer" in body
    assert "decision support tool" in body["disclaimer"].lower()


def test_history_reflects_two_turns_after_single_query():
    """Single query should append one user and one assistant turn."""
    client, _ = _build_client()
    session_id = client.post("/api/v1/assistant/session").json()["session_id"]

    upload_content = "Context text for legal analysis. " * 10
    files = {"file": ("context.txt", upload_content.encode("utf-8"), "text/plain")}
    client.post(f"/api/v1/assistant/session/{session_id}/context/upload", files=files)

    payload = {
        "session_id": session_id,
        "question": "What precedent themes are relevant here?",
    }
    query_response = client.post("/api/v1/assistant/query", json=payload)
    assert query_response.status_code == 200

    history_response = client.get(f"/api/v1/assistant/session/{session_id}/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["session_id"] == session_id
    assert len(history["messages"]) == 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"


def test_set_context_from_case_and_delete_session():
    """Case-context endpoint should work and session delete should succeed."""
    client, _ = _build_client()
    session_id = client.post("/api/v1/assistant/session").json()["session_id"]

    context_response = client.post(
        f"/api/v1/assistant/session/{session_id}/context/case/42",
        json={"include_full_text": True, "max_chars": 5000},
    )
    assert context_response.status_code == 200
    context_body = context_response.json()
    assert context_body["context"]["source"] == "case"
    assert context_body["context"]["source_ref"] == "42"

    delete_response = client.delete(f"/api/v1/assistant/session/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
