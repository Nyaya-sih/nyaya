"""Unit tests for outcome tendency explainability and bias audit."""

from datetime import date
from types import SimpleNamespace

from src.features.outcome_tendency.bias_audit import OutcomeBiasAuditEngine
from src.features.outcome_tendency.explainability import OutcomeExplainabilityEngine
from src.features.outcome_tendency.schemas import KeyFactor


def _case(**kwargs):
    base = {
        "court": "High Court of Delhi",
        "verdict": "Dismissed",
        "case_type": "Criminal",
        "date_of_judgment": date(2024, 1, 1),
        "sections_invoked": ["302 IPC"],
        "sentence": "5 years",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_explainability_signals_present_for_non_empty_cases():
    engine = OutcomeExplainabilityEngine()
    signals = engine.build_signals(
        cases=[_case(), _case(court="High Court of Bombay")],
        key_factors=[
            KeyFactor(name="Evidence quality signals", influence_percent=33.0),
            KeyFactor(name="Sections pattern", influence_percent=24.0),
        ],
        profile="criminal",
    )
    assert len(signals) == 2
    assert signals[0].factor == "Evidence quality signals"
    assert signals[0].influence_percent == 33.0
    assert signals[0].evidence_note


def test_bias_audit_handles_sparse_slices_without_crash():
    engine = OutcomeBiasAuditEngine()
    summary = engine.audit(
        cases=[_case(), _case(court="Supreme Court of India")],
        profile="criminal",
    )
    assert summary.disparity_flag is False
    assert summary.max_slice_gap_percent >= 0.0
    assert isinstance(summary.notes, list)


def test_bias_audit_skips_drift_when_year_support_is_low():
    engine = OutcomeBiasAuditEngine()
    rows = [
        _case(date_of_judgment=date(2023, 1, 1), verdict="Dismissed") for _ in range(30)
    ] + [_case(date_of_judgment=date(2024, 1, 1), verdict="Allowed") for _ in range(30)]
    summary = engine.audit(cases=rows, profile="civil")
    assert summary.drift_flag is False
    assert any("Drift check skipped" in note for note in summary.notes)
