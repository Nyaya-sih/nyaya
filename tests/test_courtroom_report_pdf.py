"""Offline PDF rendering and download contracts for canonical courtroom reports."""

from datetime import datetime, timezone
from io import BytesIO
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PyPDF2 import PdfReader
import pytest

from src.api.dependencies import get_courtroom_service
from src.features.courtroom.report_pdf import build_report_pdf
from src.features.courtroom.router import router
from src.features.courtroom.schemas import CourtroomAnalysisResponse
from src.features.courtroom.service import CourtroomRunNotFoundError


@pytest.fixture
def report():
    """Complete public snapshot; never creates services, threads or model clients."""
    explanation = {
        "conclusion_basis": "PUBLIC BASIS <b>literal</b> & reasons",
        "supporting_evidence": [
            {"source_ref": "E1", "quote": "MATCHED QUOTE", "relevance": "identity", "quote_verified": True},
            {"source_ref": "E2", "quote": "UNVERIFIED QUOTE", "relevance": "timing", "quote_verified": False},
        ],
        "assumptions": ["ASSUMPTION"], "counterarguments": ["COUNTERARGUMENT"],
        "uncertainty": ["UNCERTAINTY"], "change_summary": "CHANGE SUMMARY",
    }
    role = {
        "role_name": "defense", "analysis_text": "ORIGINAL POSITION",
        "citations": ["CITATION"], "confidence": 0.65,
        "provider": "fixture", "model": "same-model",
        "public_explanation": explanation,
        "source_evidence": [{"doc_id": "source-id", "excerpt": "FULL SUPPLIED EXCERPT"}],
    }
    return CourtroomAnalysisResponse.model_validate({
        "analysis_id": 'canonical_123"\r\nInjected: header',
        "status": "completed", "mode": "full",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "initial_role_analyses": [role],
        "role_analyses": [{**role, "analysis_text": "REBUTTAL POSITION"}],
        "rebuttal_enabled": True, "rebuttal_changes": ["REBUTTAL DELTA"],
        "synthesis": {
            "executive_summary": "SYNTHESIS", "recommended_outcome": "OUTCOME",
            "confidence": 0.7, "consensus_points": ["CONSENSUS"],
            "disagreement_points": ["DISAGREEMENT"], "unresolved_issues": ["UNRESOLVED"],
            "legal_principles_applied": ["PRINCIPLE"],
        },
        "judge_review": {
            "approved": True, "reasoning": "JUDICIAL REASONING", "confidence": 0.7,
            "required_changes": ["REQUIRED CHANGE"], "public_explanation": explanation,
        },
        "warnings": ["FIXTURE WARNING"], "disclaimer": "FIXTURE DISCLAIMER",
        "evaluation_breakdown": [{
            "evaluator_role": "prosecution", "target_role": "defense",
            "criteria_scores": {key: 75 for key in ["legal_accuracy", "constitutional_alignment", "logical_coherence", "precedent_usage", "fairness_balance", "practical_applicability"]},
            "weighted_score": 75, "justification": "PEER JUSTIFICATION",
        }],
        "trial_events": [{
            "event_id": "event-1", "session_id": "canonical_123", "stage": "judicial",
            "role": "judge", "agent_id": "judge-1", "model_provider": "fixture",
            "model_id": "same-model", "round": 1, "event_type": "vote",
            "content": "AUDIT EVENT CONTENT", "confidence": 0.7,
            "timestamp": "2026-01-02T00:00:00Z", "public_explanation": explanation,
            "citations": [{"doc_id": "E1", "section_ref": "1", "quoted_text": "EVENT CITATION"}],
        }],
    })


def extracted(pdf):
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def test_download_contract_and_all_public_sections(report):
    class Service:
        def get_analysis(self, analysis_id):
            assert analysis_id == "requested-alias"
            return report

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_courtroom_service] = lambda: Service()
    with TestClient(app) as client:
        response = client.get("/api/v1/courtroom/analysis/requested-alias/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == 'attachment; filename="courtroom-canonical_123___Injected__header.pdf"'
    assert response.content.startswith(b"%PDF-")
    text = extracted(response.content)
    for expected in [
        "NOT APPROVED", "ORIGINAL POSITION", "REBUTTAL POSITION",
        "PUBLIC BASIS <b>literal</b> & reasons", "FULL SUPPLIED EXCERPT",
        "Matched supplied source text", "NOT VERIFIED", "ASSUMPTION", "COUNTERARGUMENT",
        "UNCERTAINTY", "CHANGE SUMMARY", "JUDICIAL REASONING", "REQUIRED CHANGE",
        "CONSENSUS", "DISAGREEMENT", "UNRESOLVED", "PRINCIPLE", "FIXTURE WARNING",
        "PEER JUSTIFICATION", "AUDIT EVENT CONTENT", "EVENT CITATION", "Same-model warning",
        "Unavailable / not supplied", "2026-01-01", "2026-01-02",
    ]:
        assert expected in text


def test_unknown_analysis_is_404():
    class Service:
        def get_analysis(self, analysis_id):
            raise CourtroomRunNotFoundError("Unknown analysis")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_courtroom_service] = lambda: Service()
    with TestClient(app) as client:
        assert client.get("/api/v1/courtroom/analysis/missing/report.pdf").status_code == 404


def test_explicit_completed_approval_without_required_changes(report):
    report.judge_review.required_changes = []
    assert "SIMULATED JUDGE APPROVED" in extracted(build_report_pdf(report))


@pytest.mark.parametrize("status", ["queued", "running", "failed", "cancelled", "degraded"])
def test_noncompleted_is_never_approved(report, status):
    report.status = status
    text = extracted(build_report_pdf(report))
    assert "SIMULATED JUDGE APPROVED" not in text
    assert "NOT APPROVED" in text
    if status in {"queued", "running"}:
        assert "INCOMPLETE / NOT APPROVED" in text


@pytest.mark.parametrize("degraded", ["role", "original", "judge", "synthesis", "not_approved", "no_judge", "no_synthesis"])
def test_approval_requires_explicit_healthy_gate(report, degraded):
    if degraded == "role":
        report.role_analyses[0].degraded = True
    elif degraded == "original":
        report.initial_role_analyses[0].degraded = True
    elif degraded == "judge":
        report.judge_review.degraded = True
    elif degraded == "synthesis":
        report.synthesis.degraded = True
    elif degraded == "not_approved":
        report.judge_review.approved = False
    elif degraded == "no_judge":
        report.judge_review = None
    else:
        report.synthesis = None
    assert "SIMULATED JUDGE APPROVED" not in extracted(build_report_pdf(report))


def test_long_untrusted_text_and_unicode(report, tmp_path):
    report.role_analyses[0].analysis_text = (
        "LONG START <img src='file:///etc/passwd'/> & <broken>\n"
        + "Long public paragraph containing all supplied text. " * 1500
        + "\nLONG END\n"
        + "Unicode: \u00a7 \u2014 \u00e9 \U0001f9d1"
    )
    report.role_analyses[0].source_evidence[0]["doc_id"] = "Z" * 5000
    report.trial_events[0].content = "EVENT FIRST " + "event body " * 1800 + " EVENT LAST"
    pdf = build_report_pdf(report)
    path = tmp_path / "long-report.pdf"
    path.write_bytes(pdf)
    reader = PdfReader(BytesIO(pdf))
    text = extracted(pdf)
    assert len(reader.pages) > 20
    assert "LONG START <img src='file:///etc/passwd'/> & <broken>" in text
    assert "LONG END" in text and "EVENT LAST" in text
    # Page furniture can intervene between words in extracted cross-page text.
    assert text.count("Long") == 1500
    assert text.count("paragraph") == 1500
    assert sum(len(run) for run in re.findall(r"Z{2,}", text)) == 5000
    assert "[U+1F9D1]" in text
    assert "\u00a7" in text and "\u00e9" in text
    for page in reader.pages:
        assert float(page.mediabox.width) == pytest.approx(595.2756, abs=0.01)


def test_bundled_font_fallback(report, monkeypatch):
    original = __import__("pathlib").Path.is_file
    monkeypatch.setattr("pathlib.Path.is_file", lambda path: False if "DejaVuSans" in path.name else original(path))
    assert "Vera.ttf" in extracted(build_report_pdf(report))
