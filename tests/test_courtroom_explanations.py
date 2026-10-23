"""Mocked public explanation, grounding, prompt and event contract tests."""

import json

import pytest

from src.config.settings import settings
from src.features.courtroom.analysis_engine import CourtroomAnalysisEngine
from src.features.courtroom.model_registry import ModelRoute
from src.features.courtroom.public_explanation import validate_public_explanation
from src.features.courtroom.rebuttal_engine import CourtroomRebuttalEngine
from src.features.courtroom.roles import (
    QUICK_MODE_ROLES, ROLE_MANDATES, build_role_system_prompt, build_role_user_prompt,
)
from src.features.courtroom.schemas import CourtroomRoleAnalysis, CourtroomSynthesis
from src.features.courtroom.service import CourtroomService
from src.features.courtroom.synthesis_engine import CourtroomSynthesisEngine
from src.utils.llm_client import LLMClient


CASE = "The witness did not identify the accused at the hearing."
ROUTE = ModelRoute("openai", "test-model")


def explanation(**updates):
    return {
        "conclusion_basis": "Identification remains disputed.",
        "supporting_evidence": [{"source_ref": "case_text", "quote": CASE,
                                 "relevance": "Identification gap", "quote_verified": True}],
        "assumptions": ["No additional identification evidence supplied."],
        "counterarguments": ["Other evidence might establish identity."],
        "uncertainty": ["The full evidentiary record is unavailable."],
        "change_summary": "Retained position because the identification gap remains.",
        **updates,
    }


@pytest.mark.parametrize("source,quote,expected", [
    ("case_text", CASE, True),
    ("case_text", "The witness  did\n not identify the accused", True),
    ("case_text", "The witness identified the accused.", False),
    ("case_text", "witness", False),
    ("Invented case p. 3", CASE, False),
    ("case_text p. 3", CASE, False),
])
def test_quote_matching_ignores_model_verification(source, quote, expected):
    value = explanation(supporting_evidence=[{
        "source_ref": source, "quote": quote, "relevance": "Identity", "quote_verified": not expected,
    }])
    result, warnings = validate_public_explanation(value, CASE)
    assert result.supporting_evidence[0].quote_verified is expected
    assert result.supporting_evidence[0].source_ref == (source if expected else "unverified")
    assert bool(warnings) is not expected


def test_only_supplied_retrieval_excerpt_can_verify():
    blocks = [{"citation_id": "LAW-1", "excerpt": "The burden rests upon the prosecution."}]
    value = explanation(supporting_evidence=[{
        "source_ref": "LAW-1", "quote": blocks[0]["excerpt"], "relevance": "Burden",
    }])
    result, _ = validate_public_explanation(value, CASE, blocks)
    assert result.supporting_evidence[0].quote_verified
    result, warnings = validate_public_explanation(value, CASE)
    assert not result.supporting_evidence[0].quote_verified and warnings
    blocks[0]["excerpt"] = "x" * 501 + "Hidden quotation beyond supplied excerpt."
    value["supporting_evidence"][0]["quote"] = "Hidden quotation beyond supplied excerpt."
    result, _ = validate_public_explanation(value, CASE, blocks)
    assert not result.supporting_evidence[0].quote_verified


@pytest.mark.parametrize("source", ["PDF page 2", "[PDF page 2]", "PDF page 99"])
def test_text_markers_cannot_authenticate_pdf_page_provenance(source):
    case = f"[PDF page 1]\nA different account.\n[PDF page 2]\n{CASE}"
    value = explanation(supporting_evidence=[{"source_ref": source, "quote": CASE, "relevance": "Identity"}])
    result, warnings = validate_public_explanation(value, case)
    assert warnings
    assert result.supporting_evidence[0].source_ref == "unverified"
    assert not result.supporting_evidence[0].quote_verified


def test_pdf_quote_on_wrong_page_is_not_verified():
    case = f"[PDF page 1]\nA different account.\n[PDF page 2]\n{CASE}"
    value = explanation(supporting_evidence=[{"source_ref": "PDF page 1", "quote": CASE, "relevance": "Identity"}])
    result, warnings = validate_public_explanation(value, case)
    assert warnings and not result.supporting_evidence[0].quote_verified


def test_case_quote_remains_case_text_despite_spoofed_page_marker():
    case = f"[PDF page 99]\n{CASE}"
    result, warnings = validate_public_explanation(explanation(), case)
    assert not warnings
    assert result.supporting_evidence[0].quote_verified
    assert result.supporting_evidence[0].source_ref == "case_text"


@pytest.mark.parametrize("value", [None, {}, {"conclusion_basis": ""}])
def test_missing_or_invalid_explanation_fails_closed(value):
    result, warnings = validate_public_explanation(value, CASE)
    assert result is None and warnings


def enable_mock(monkeypatch, engine, output):
    monkeypatch.setattr(settings, "courtroom_enable_live_llm", True)
    engine.live_enabled = True
    monkeypatch.setattr(engine.registry, "get_chain", lambda role: [ROUTE])
    calls = []

    def generate(self, **kwargs):
        calls.append(kwargs)
        return json.dumps(output)

    monkeypatch.setattr(LLMClient, "generate", generate)
    return calls


@pytest.mark.parametrize("role", QUICK_MODE_ROLES)
def test_independent_role_prompt_and_server_explanation(monkeypatch, role):
    engine = CourtroomAnalysisEngine()
    calls = enable_mock(monkeypatch, engine, {
        "analysis_text": "Identity disputed.", "confidence": 0.83,
        "public_explanation": explanation(),
    })
    result = engine.run_role(role, CASE, "quick")
    assert result.analysis.public_explanation.supporting_evidence[0].quote_verified
    assert result.analysis.confidence == 0.83
    assert result.analysis.confidence_kind == "model_self_assessment"
    prompt = calls[0]["system_prompt"] + calls[0]["prompt"]
    for term in ["public_explanation", "assumptions", "counterarguments", "uncertainty",
                 "strongest counterargument", "private chain-of-thought", "retained"]:
        assert term in prompt
    assert "Shared initial opinions" not in prompt
    assert calls[0]["max_tokens"] == 1200
    assert ROLE_MANDATES[role] in calls[0]["system_prompt"]


def test_omitted_role_explanation_emits_warning(monkeypatch):
    engine = CourtroomAnalysisEngine()
    enable_mock(monkeypatch, engine, {"analysis_text": "No explanation", "confidence": 0.7})
    result = engine.run_role("Defense Counsel", CASE, "quick")
    assert result.analysis.public_explanation is None
    assert any("public explanation" in w for w in result.warnings)


@pytest.mark.parametrize("role_name", QUICK_MODE_ROLES)
def test_rebuttal_retains_public_change_reasons_and_fallback_is_empty(monkeypatch, role_name):
    engine = CourtroomRebuttalEngine()
    calls = enable_mock(monkeypatch, engine, {
        "analysis_text": "Retained opinion", "confidence": 0.7, "public_explanation": explanation(),
    })
    role = CourtroomRoleAnalysis(role_name=role_name, analysis_text="Initial", confidence=0.8)
    updated, note, warnings = engine._revise_role(role, json.dumps([role.model_dump()]), CASE)
    assert updated.public_explanation.change_summary in note
    assert not warnings
    assert "public_explanation" in calls[0]["prompt"]
    assert "strongest counterargument" in calls[0]["system_prompt"]
    assert ROLE_MANDATES[role_name] in calls[0]["system_prompt"]
    assert calls[0]["max_tokens"] == 1000
    engine.live_enabled = False
    fallback, _, _ = engine._revise_role(updated, "[]", CASE)
    assert fallback.public_explanation is None


def test_moral_advisor_separates_ethics_from_law_and_preserves_rights():
    prompt = build_role_system_prompt("Moral Advisor")
    for safeguard in [
        "ethical opinions", "value tradeoffs", "enforceable Indian law",
        "Do not recommend moral punishment", "constitutional rights",
        "due process", "presumption of innocence",
        "moral disapproval is not evidence of legal guilt",
    ]:
        assert safeguard in prompt


def test_retrieval_sources_survive_rebuttal_and_judge_review(monkeypatch):
    blocks = [
        {"citation_id": "LAW-1", "excerpt": "An unrelated excerpt under the same authority."},
        {"citation_id": "LAW-1", "excerpt": "The burden rests upon the prosecution."},
    ]
    value = explanation(supporting_evidence=[{
        "source_ref": "LAW-1", "quote": blocks[1]["excerpt"], "relevance": "Burden",
    }])
    grounded, _ = validate_public_explanation(value, CASE, blocks)
    role = CourtroomRoleAnalysis(
        role_name="Defense Counsel", analysis_text="Initial", confidence=0.8,
        public_explanation=grounded, source_evidence=blocks,
    )
    rebuttal = CourtroomRebuttalEngine()
    enable_mock(monkeypatch, rebuttal, {
        "analysis_text": "Retained opinion", "confidence": 0.7,
        "public_explanation": value, "source_evidence": [{"citation_id": "invented"}],
    })
    updated, _, warnings = rebuttal._revise_role(role, json.dumps([role.model_dump()]), CASE)
    assert not warnings
    assert updated.public_explanation.supporting_evidence[0].quote_verified
    assert updated.source_evidence == blocks
    judge = CourtroomSynthesisEngine()
    enable_mock(monkeypatch, judge, {
        "approved": True, "reasoning": "Reviewed supplied authorities", "required_changes": [],
        "confidence": 0.8, "public_explanation": value,
    })
    review, warnings = judge.review(
        case_text=CASE, initial_role_analyses=[role], role_analyses=[updated],
        synthesis=CourtroomSynthesis(executive_summary="Draft", recommended_outcome="Review", confidence=0.8),
    )
    assert not warnings and review.approved
    assert review.public_explanation.supporting_evidence[0].quote_verified


@pytest.mark.parametrize("problem", [None, "missing", "unverified", "change", "empty_evidence"])
def test_judge_approval_gated_by_explanations(monkeypatch, problem):
    engine = CourtroomSynthesisEngine()
    calls = enable_mock(monkeypatch, engine, {
        "approved": True, "reasoning": "Record reviewed", "required_changes": [],
        "confidence": 0.81, "public_explanation": explanation(),
    })
    grounded, _ = validate_public_explanation(explanation(), CASE)
    role = CourtroomRoleAnalysis(role_name="Defense Counsel", analysis_text="Opinion",
                                 confidence=0.8, public_explanation=grounded)
    if problem == "missing":
        role.public_explanation = None
    elif problem == "unverified":
        role.public_explanation.supporting_evidence[0].quote_verified = False
    elif problem == "change":
        role.public_explanation.change_summary = None
    elif problem == "empty_evidence":
        role.public_explanation.supporting_evidence = []
    review, _ = engine.review(case_text=CASE, initial_role_analyses=[role], role_analyses=[role],
                              synthesis=CourtroomSynthesis(executive_summary="Draft",
                              recommended_outcome="Review evidence", confidence=0.8))
    assert review.approved is (problem is None)
    assert bool(review.required_changes) is (problem is not None)
    assert review.public_explanation.supporting_evidence[0].quote_verified
    prompt = json.loads(calls[0]["prompt"])
    assert prompt["case_material"] == CASE
    assert "public_explanation" in prompt["initial_opinions"][0]
    assert "public_explanation" in prompt["output_schema"]
    assert calls[0]["max_tokens"] == 1000


@pytest.mark.parametrize("kind,stage,round_number", [
    ("position", "group_deliberation", 1), ("rebuttal", "rebuttal", 2), ("vote", "judicial", 4),
])
def test_public_explanation_survives_event_persistence_and_report(kind, stage, round_number):
    service = CourtroomService()
    run = service.store.create_run("quick", True, "text", "source")
    grounded, _ = validate_public_explanation(explanation(), CASE)
    event = service._record_trial_event(
        analysis_id=run.analysis_id, stage=stage, role="Defense Counsel", agent_id="defense",
        model_provider="openai", model_id="test", round_number=round_number,
        event_type=kind, content="Public position", citations=[], confidence=0.81,
        public_explanation=grounded,
    )
    assert service.get_trial_events(run.analysis_id)[0]["public_explanation"] == grounded.model_dump()
    assert service.get_analysis(run.analysis_id).trial_events[0].public_explanation == grounded
    assert event.confidence == 0.81 and event.confidence_kind == "model_self_assessment"
