"""Bias and disparity checks for outcome tendency cohorts."""

from __future__ import annotations

from collections import Counter, defaultdict

from src.database.models import Case
from src.features.outcome_tendency.schemas import BiasAuditSummary, BiasSliceMetric


class OutcomeBiasAuditEngine:
    """Runs simple slice-level disparity and drift checks."""

    DISPARITY_THRESHOLD_PERCENT = 25.0
    MIN_SLICE_SIZE = 20
    DRIFT_MIN_YEAR_SAMPLE = 40
    DRIFT_THRESHOLD_PERCENT = 30.0

    def audit(self, cases: list[Case], profile: str) -> BiasAuditSummary:
        """Audit cohort slices and emit disparity notes."""
        if not cases:
            return BiasAuditSummary(
                disparity_flag=False,
                drift_flag=False,
                max_slice_gap_percent=0.0,
                slice_metrics=[],
                notes=[
                    "Bias audit uses baseline assumptions due to sparse or missing cohort."
                ],
            )

        by_slice: dict[str, list[Case]] = defaultdict(list)
        for item in cases:
            level = self._court_level((item.court or "").lower())
            by_slice[f"court_level:{level}"].append(item)

        metrics: list[BiasSliceMetric] = []
        for name, rows in by_slice.items():
            if len(rows) < self.MIN_SLICE_SIZE:
                continue
            dominant_label, dominant_rate = self._dominant_rate(rows, profile)
            metrics.append(
                BiasSliceMetric(
                    slice_name=name,
                    dominant_outcome=dominant_label,
                    dominant_rate_percent=round(dominant_rate, 1),
                    sample_size=len(rows),
                )
            )

        if not metrics:
            return BiasAuditSummary(
                disparity_flag=False,
                drift_flag=False,
                max_slice_gap_percent=0.0,
                slice_metrics=[],
                notes=["Insufficient per-slice sample support for disparity analysis."],
            )

        rates = [item.dominant_rate_percent for item in metrics]
        max_gap = max(rates) - min(rates)
        disparity_flag = max_gap >= self.DISPARITY_THRESHOLD_PERCENT

        notes = [
            f"Slice disparity check executed across {len(metrics)} slices.",
            f"Maximum dominant-outcome gap observed: {max_gap:.1f}%.",
        ]
        if disparity_flag:
            notes.append(
                "Disparity flag triggered; interpret tendency with heightened caution across slice groups."
            )

        # Drift check: recent two years concentration shift with minimum support.
        years = sorted(
            {
                item.date_of_judgment.year
                for item in cases
                if item.date_of_judgment is not None
            }
        )
        drift_flag = False
        if len(years) >= 2:
            recent = years[-1]
            prior = years[-2]
            recent_rows = [
                item
                for item in cases
                if item.date_of_judgment and item.date_of_judgment.year == recent
            ]
            prior_rows = [
                item
                for item in cases
                if item.date_of_judgment and item.date_of_judgment.year == prior
            ]
            if (
                len(recent_rows) >= self.DRIFT_MIN_YEAR_SAMPLE
                and len(prior_rows) >= self.DRIFT_MIN_YEAR_SAMPLE
            ):
                _, recent_rate = self._dominant_rate(recent_rows, profile)
                _, prior_rate = self._dominant_rate(prior_rows, profile)
                drift_flag = (
                    abs(recent_rate - prior_rate) >= self.DRIFT_THRESHOLD_PERCENT
                )
                if drift_flag:
                    notes.append(
                        "Recent-year dominant outcome shifted materially versus prior year (drift flag)."
                    )
            else:
                notes.append(
                    "Drift check skipped due to limited year-wise sample support."
                )

        return BiasAuditSummary(
            disparity_flag=disparity_flag,
            drift_flag=drift_flag,
            max_slice_gap_percent=round(max_gap, 1),
            slice_metrics=metrics,
            notes=notes,
        )

    def _court_level(self, court: str) -> str:
        if "supreme" in court:
            return "supreme"
        if "high court" in court or "hc" in court:
            return "high"
        if "district" in court or "sessions" in court:
            return "district"
        return "other"

    def _dominant_rate(self, rows: list[Case], profile: str) -> tuple[str, float]:
        verdict_counter: Counter[str] = Counter()
        for item in rows:
            verdict_counter[self._normalize_verdict(item.verdict or "", profile)] += 1
        if not verdict_counter:
            return "Other", 0.0
        label, count = verdict_counter.most_common(1)[0]
        return label, (count / max(1, len(rows))) * 100.0

    def _normalize_verdict(self, verdict: str, profile: str) -> str:
        value = verdict.strip().lower()
        if profile in {"criminal", "economic"}:
            if "convict" in value:
                return "Convicted"
            if "acquit" in value:
                return "Acquitted"
            if "dismiss" in value:
                return "Dismissed"
            return "Other"
        if profile == "constitutional":
            if "allow" in value:
                return "Petition Allowed"
            if "dismiss" in value:
                return "Petition Dismissed"
            if "part" in value:
                return "Partially Allowed"
            return "Other"
        if "allow" in value:
            return "Suit Allowed"
        if "dismiss" in value:
            return "Suit Dismissed"
        if "part" in value:
            return "Partially Allowed"
        return "Other"
