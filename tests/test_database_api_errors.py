"""Database outages should produce actionable API responses, not CORS failures."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import OperationalError, TimeoutError

from src.api import dependencies
from src.api.middleware import request_logging_middleware
from src.features.similar_cases.router import router


@pytest.mark.parametrize("failure", [
    OperationalError("SELECT", {}, Exception("private connection details")),
    TimeoutError("private connection details"),
])
def test_filters_database_outage_has_cors_and_closes_resources(monkeypatch, failure):
    calls = []

    class Session:
        def query(self, *args, **kwargs):
            raise failure

        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    class Engine:
        def dispose(self):
            calls.append("dispose")

    monkeypatch.setattr(dependencies, "create_engine", lambda *a, **kw: Engine())
    monkeypatch.setattr(dependencies, "sessionmaker", lambda **kw: Session)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:3020"])
    app.middleware("http")(request_logging_middleware)
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cases/search/filters",
            headers={"Origin": "http://127.0.0.1:3020"},
        )
        rejected_origin = client.get(
            "/api/v1/cases/search/filters",
            headers={"Origin": "https://untrusted.example"},
        )
    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3020"
    assert "DATABASE_URL" in response.json()["detail"]
    assert "private connection details" not in response.text
    assert "access-control-allow-origin" not in rejected_origin.headers
    assert calls == ["rollback", "close", "dispose"] * 2
