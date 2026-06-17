"""Confidence calibration helpers for outcome tendency analysis."""

from __future__ import annotations

import math

from src.features.outcome_tendency.schemas import ConfidenceBand, OutcomeBucket


class OutcomeCalibrationEngine:
    """Builds confidence context using sample support and distribution shape."""

    def build_confidence_band(
        self,
        outcome_distribution: list[OutcomeBucket],
        sample_size: int,
        mode: str,
    ) -> ConfidenceBand:
        """Return a calibrated confidence band for dominant outcome tendency."""
        if sample_size <= 0 or not outcome_distribution:
            return ConfidenceBand(
                level="low",
                lower_bound=0.0,
                upper_bound=0.0,
                method="insufficient_data",
                reliability_score=0.0,
            )

        dominant = max(outcome_distribution, key=lambda item: item.percentage)
        p = max(0.0, min(1.0, dominant.percentage / 100.0))
        z = 1.96 if mode == "baseline" else 1.64
        margin = z * math.sqrt((p * (1.0 - p)) / max(1, sample_size))

        lower = max(0.0, (p - margin) * 100.0)
        upper = min(100.0, (p + margin) * 100.0)

        entropy = 0.0
        for bucket in outcome_distribution:
            prob = max(0.0, min(1.0, bucket.percentage / 100.0))
            if prob > 0:
                entropy -= prob * math.log(prob, 2)
        max_entropy = math.log(max(2, len(outcome_distribution)), 2)
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 1.0

        sample_factor = min(1.0, sample_size / 600.0)
        concentration = p
        reliability = (
            0.45 * sample_factor
            + 0.35 * concentration
            + 0.20 * (1.0 - normalized_entropy)
        )
        reliability = max(0.0, min(1.0, reliability))

        if reliability >= 0.72:
            level = "high"
        elif reliability >= 0.5:
            level = "medium"
        else:
            level = "low"

        return ConfidenceBand(
            level=level,
            lower_bound=round(lower, 1),
            upper_bound=round(upper, 1),
            method="wilson_approx_dominant_class",
            reliability_score=round(reliability, 3),
        )
