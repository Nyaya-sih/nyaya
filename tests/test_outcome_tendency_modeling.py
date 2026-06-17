"""Unit tests for outcome tendency feature/model utilities."""

from datetime import date
from types import SimpleNamespace

from src.features.outcome_tendency.feature_builder import OutcomeFeatureBuilder
from src.features.outcome_tendency.model_runner import OutcomeModelRunner


def _case(**kwargs):
    base = {
        "verdict": "Convicted",
        "case_type": "Criminal",
        "court": "High Court of Delhi",
        "date_of_judgment": date(2022, 5, 4),
        "sections_invoked": ["302 IPC"],
        "charges": ["Murder"],
        "headnotes": ["Bail", "Evidence"],
        "sentence": "7 years",
        "case_title": "State vs X",
        "court_reasoning": "Reasoning text " * 8,
        "validation_status": "valid",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_feature_builder_extracts_rows_and_targets():
    builder = OutcomeFeatureBuilder()
    rows_targets = builder.build(
        [
            _case(verdict="Convicted"),
            _case(verdict="Acquitted", sentence=""),
            _case(verdict="Petition Allowed", case_type="Constitutional"),
        ]
    )

    assert len(rows_targets.rows) == 3
    assert len(rows_targets.targets) == 3
    assert "convicted" in rows_targets.targets
    assert "acquitted" in rows_targets.targets
    assert "allowed" in rows_targets.targets
    assert rows_targets.rows[0]["sections_count"] == 1
    assert rows_targets.rows[1]["has_sentence"] == 0


def test_model_runner_returns_insufficient_data_for_small_dataset():
    runner = OutcomeModelRunner()
    rows = [{"year": 2020, "case_type": "criminal"} for _ in range(20)]
    targets = ["convicted" for _ in range(20)]

    result = runner.benchmark(rows, targets)
    assert result["status"] == "insufficient_data"


def test_model_runner_benchmark_ok_for_balanced_dataset():
    runner = OutcomeModelRunner()
    rows = []
    targets = []
    for i in range(120):
        rows.append(
            {
                "year": 2018 + (i % 6),
                "case_type": "criminal" if i % 2 == 0 else "civil",
                "court_level": "high" if i % 3 else "district",
                "sections_count": 2 + (i % 4),
                "charges_count": 1 + (i % 3),
                "has_sentence": 1 if i % 2 == 0 else 0,
                "reasoning_len": 120 + i,
                "text_len": 200 + i,
                "validation_status": "valid",
            }
        )
        targets.append("convicted" if i % 2 == 0 else "dismissed")

    result = runner.benchmark(rows, targets)
    assert result["status"] == "ok"
    assert result["sample_size"] == 120
    assert len(result["results"]) >= 3
