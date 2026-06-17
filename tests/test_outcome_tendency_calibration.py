"""Unit tests for outcome tendency confidence calibration."""

from src.features.outcome_tendency.calibration import OutcomeCalibrationEngine
from src.features.outcome_tendency.schemas import OutcomeBucket


def test_calibration_outputs_reliable_shape():
    engine = OutcomeCalibrationEngine()
    band = engine.build_confidence_band(
        outcome_distribution=[
            OutcomeBucket(label="Convicted", count=580, percentage=58.0),
            OutcomeBucket(label="Acquitted", count=280, percentage=28.0),
            OutcomeBucket(label="Other", count=140, percentage=14.0),
        ],
        sample_size=1000,
        mode="baseline",
    )

    assert band.method == "wilson_approx_dominant_class"
    assert 0.0 <= band.reliability_score <= 1.0
    assert band.lower_bound <= band.upper_bound


def test_calibration_handles_empty_distribution():
    engine = OutcomeCalibrationEngine()
    band = engine.build_confidence_band(
        outcome_distribution=[],
        sample_size=0,
        mode="baseline",
    )

    assert band.level == "low"
    assert band.method == "insufficient_data"
    assert band.reliability_score == 0.0
