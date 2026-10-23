"""Deterministic background lifecycle tests; no external model requests."""

import json
import time
from threading import BoundedSemaphore, Event
from types import SimpleNamespace

import pytest

from src.config.settings import settings
from src.features.courtroom.analysis_engine import RoleAnalysisResult
from src.features.courtroom.model_registry import CourtroomModelRegistry
from src.features.courtroom.retrieval_adapter import CourtroomRetrievalAdapter
from src.features.courtroom.roles import QUICK_MODE_ROLES, FULL_MODE_ROLES
from src.features.courtroom.schemas import (
    CourtroomAnalyzeRequest, CourtroomJudgeReview, CourtroomRoleAnalysis,
    CourtroomSynthesis,
)
from src.features.courtroom.service import CourtroomService, CourtroomCapacityError
from src.utils.llm_client import LLMClient


def wait_terminal(service, analysis_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        report = service.get_analysis(analysis_id)
        if report.status not in {"queued", "running"}:
            return report
        time.sleep(0.005)
    raise AssertionError("Background run did not finish")


def configure(monkeypatch, *, approved=True, degraded=False):
    service = CourtroomService()
    monkeypatch.setattr(service.orchestrator.retrieval_adapter, "retrieve_for_role",
                        lambda **kw: ([], []))

    def run_role(role_name, **kw):
        return RoleAnalysisResult(CourtroomRoleAnalysis(
            role_name=role_name, analysis_text=f"Initial {role_name}", confidence=0.8,
            provider="openai", model="test-model", degraded=degraded,
        ), [])

    monkeypatch.setattr(service.orchestrator.analysis_engine, "run_role", run_role)
    snapshots = []

    def revise(item, snapshot, case_text):
        snapshots.append(snapshot)
        return item.model_copy(update={"analysis_text": f"Rebuttal {item.role_name}"}), "Reviewed", []

    monkeypatch.setattr(service.rebuttal_engine, "_revise_role", revise)
    monkeypatch.setattr(service.evaluation_engine, "run_peer_evaluation", lambda *a, **kw: ([], []))
    monkeypatch.setattr(service.synthesis_engine, "synthesize", lambda **kw: (
        CourtroomSynthesis(executive_summary="Draft", recommended_outcome="Outcome", confidence=0.8), []
    ))
    monkeypatch.setattr(service.synthesis_engine, "review", lambda **kw: (
        CourtroomJudgeReview(approved=approved, reasoning="Reviewed record", confidence=0.8,
                             provider="openai", model="test-model"), []
    ))
    return service, snapshots


@pytest.mark.parametrize("mode,roles", [("quick", QUICK_MODE_ROLES), ("full", FULL_MODE_ROLES)])
def test_live_order_and_shared_snapshot(monkeypatch, mode, roles):
    service, snapshots = configure(monkeypatch)
    created = service.create_analysis(CourtroomAnalyzeRequest(mode=mode, include_rebuttal=False))
    assert created.status == "queued"
    report = wait_terminal(service, created.analysis_id)
    assert report.status == "completed"
    assert report.rebuttal_enabled
    assert len(roles) == 5
    assert len(report.initial_role_analyses) == len(report.role_analyses) == 5
    assert {"Constitutional Expert", "Moral Advisor"}.issubset(roles)
    assert len(snapshots) == len(roles)
    assert len(set(snapshots)) == 1
    assert [r["role_name"] for r in json.loads(snapshots[0])] == roles
    assert all(r.analysis_text.startswith("Initial") for r in report.initial_role_analyses)
    assert all(r.analysis_text.startswith("Rebuttal") for r in report.role_analyses)
    events = report.trial_events
    types = [e.event_type for e in events]
    assert types[-4:] == ["synthesis", "frame", "vote", "verdict"]
    assert all(e.role == "Presiding Judge" for e in events[-3:])
    for role in roles:
        own = [(i, e) for i, e in enumerate(events) if e.role == role]
        assert [e.event_type for _, e in own] == ["frame", "position", "frame", "rebuttal"]
        assert own[-1][1].responding_to == own[1][1].event_id
    assert max(i for i, e in enumerate(events) if e.event_type == "position") < min(
        i for i, e in enumerate(events) if e.stage == "rebuttal"
    )


@pytest.mark.parametrize("approved,degraded", [(False, False), (True, True)])
def test_rejection_or_degraded_material_never_emits_verdict(monkeypatch, approved, degraded):
    service, _ = configure(monkeypatch, approved=approved, degraded=degraded)
    run = service.create_analysis(CourtroomAnalyzeRequest())
    report = wait_terminal(service, run.analysis_id)
    assert report.judge_review.approved is False
    assert report.trial_events[-1].event_type == "vote"
    assert not any(e.event_type == "verdict" for e in report.trial_events)
    assert report.status == ("degraded" if degraded else "completed")


def test_early_return_partial_report_and_cancellation(monkeypatch):
    service, _ = configure(monkeypatch)
    started, release, finished = Event(), Event(), Event()
    original = service.orchestrator.analysis_engine.run_role

    def blocked(**kw):
        started.set()
        assert release.wait(5)
        return original(**kw)

    monkeypatch.setattr(service.orchestrator.analysis_engine, "run_role", blocked)
    original_background = service._run_background

    def background(*args):
        try:
            original_background(*args)
        finally:
            finished.set()

    monkeypatch.setattr(service, "_run_background", background)
    run = service.create_analysis(CourtroomAnalyzeRequest())
    try:
        assert run.status == "queued"
        assert started.wait(3)
        report = service.get_analysis(run.analysis_id)
        assert report.status == "running"
        assert report.synthesis is None and report.judge_review is None
        assert report.transparency_dashboard is None
        assert any(e.event_type == "frame" and e.round == 1 for e in report.trial_events)
        assert service.cancel_analysis(run.analysis_id).cancelled
        before = service.get_analysis(run.analysis_id)
    finally:
        release.set()
    assert finished.wait(3)
    after = service.get_analysis(run.analysis_id)
    assert after == before
    assert after.status == "cancelled" and after.completed_at is not None


def test_background_exception_marks_failed(monkeypatch):
    service, _ = configure(monkeypatch)

    def fail(**kw):
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(service.synthesis_engine, "synthesize", fail)
    run = service.create_analysis(CourtroomAnalyzeRequest())
    report = wait_terminal(service, run.analysis_id)
    assert report.status == "failed"
    assert report.completed_at is not None
    assert "controlled failure" in report.warnings[-1]
    assert not any(e.event_type == "verdict" for e in report.trial_events)


def test_model_pin_ignores_provider_and_request_overrides(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-only")
    monkeypatch.setattr(settings, "extraction_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "courtroom_role_model_map", '{"Defense Counsel": []}')
    registry = CourtroomModelRegistry(role_override_map={
        "Defense Counsel": [{"provider": "anthropic", "model": "other"}],
    })
    for role in FULL_MODE_ROLES + ["Presiding Judge"]:
        assert registry.get_chain(role) == [registry.route]
        assert registry.route.provider == "openai"
        assert registry.route.model == "gpt-4o-mini"
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert registry.get_chain("Presiding Judge") == []


@pytest.mark.parametrize("role", FULL_MODE_ROLES)
def test_each_deliberator_uses_role_specific_retrieval(monkeypatch, role):
    adapter = CourtroomRetrievalAdapter()
    adapter.enabled = True
    queries = []

    def parse(query):
        queries.append(query)
        return SimpleNamespace(statutes_hint=[], sections_hint=[])

    def retrieve(**kwargs):
        assert kwargs["question"] == queries[-1]
        return []

    monkeypatch.setattr(adapter.query_parser, "parse", parse)
    monkeypatch.setattr(adapter.retriever, "retrieve", retrieve)
    adapter.retrieve_for_role(role_name=role, case_text="Case facts", top_k_legal=3)
    assert queries == [f"Case facts\n\n{adapter.ROLE_QUERY_SUFFIX[role]}"]


@pytest.mark.parametrize("model", ["o3", "o4-mini", "gpt-5", "gemini-pro"])
def test_incompatible_model_uses_shared_compatible_default(monkeypatch, model):
    monkeypatch.setattr(settings, "extraction_model", model)
    registry = CourtroomModelRegistry()
    assert registry.route.provider == "openai"
    assert registry.route.model == "gpt-4o-mini"


def test_queue_capacity_is_bounded(monkeypatch):
    service, _ = configure(monkeypatch)
    gate = BoundedSemaphore(1)
    gate.acquire()
    monkeypatch.setattr(service, "_capacity", gate)
    with pytest.raises(CourtroomCapacityError):
        service.create_analysis(CourtroomAnalyzeRequest())


def test_degraded_runs_can_be_retried(monkeypatch):
    service, _ = configure(monkeypatch, degraded=True)
    first = service.create_analysis(CourtroomAnalyzeRequest())
    assert wait_terminal(service, first.analysis_id).status == "degraded"
    second = service.create_analysis(CourtroomAnalyzeRequest())
    assert second.analysis_id != first.analysis_id
    assert wait_terminal(service, second.analysis_id).status == "degraded"


def test_live_setting_gates_every_engine_even_when_runtime_enabled(monkeypatch):
    service = CourtroomService()
    monkeypatch.setattr(settings, "courtroom_enable_live_llm", False)
    monkeypatch.setattr(settings, "openai_api_key", "test-only")
    for engine in [service.orchestrator.analysis_engine, service.rebuttal_engine,
                   service.evaluation_engine, service.synthesis_engine]:
        engine.live_enabled = True
    service.orchestrator.retrieval_adapter.enabled = False
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError("No model request is allowed")

    monkeypatch.setattr(LLMClient, "generate", forbidden)
    run = service.create_analysis(CourtroomAnalyzeRequest())
    report = wait_terminal(service, run.analysis_id)
    assert calls == []
    assert report.status == "degraded"
    assert all(r.degraded for r in report.initial_role_analyses + report.role_analyses)
    assert report.synthesis.degraded and report.judge_review.degraded
    assert report.judge_review.approved is False
    assert report.trial_events[-1].event_type == "vote"
