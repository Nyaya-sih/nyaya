"""Statistical computations for outcome tendency responses."""

from __future__ import annotations

from collections import Counter, defaultdict
import re

from src.database.models import Case
from src.features.outcome_tendency.schemas import (
    ConfidenceBand,
    KeyFactor,
    OutcomeBucket,
    SentenceDistribution,
    TrendPoint,
)


class OutcomeTendencyStatsEngine:
    """Computes distributions, trends, and confidence context from cohorts."""

    def build_outcome_distribution(
        self, cases: list[Case], profile: str
    ) -> list[OutcomeBucket]:
        if not cases:
            return []

        bucket_counts: Counter[str] = Counter()
        for item in cases:
            label = self._normalize_verdict(item.verdict or "", profile)
            bucket_counts[label] += 1

        total = len(cases)
        return [
            OutcomeBucket(
                label=label,
                count=count,
                percentage=round((count / total) * 100.0, 1),
            )
            for label, count in bucket_counts.most_common()
        ]

    def build_sentence_distribution(
        self, cases: list[Case]
    ) -> SentenceDistribution | None:
        years = [self._extract_sentence_years(item.sentence) for item in cases]
        values = sorted([value for value in years if value is not None])
        if not values:
            return None

        mid = len(values) // 2
        if len(values) % 2 == 0:
            median = (values[mid - 1] + values[mid]) / 2
        else:
            median = values[mid]

        return SentenceDistribution(
            average_years=round(sum(values) / len(values), 2),
            median_years=round(median, 2),
            min_years=round(values[0], 2),
            max_years=round(values[-1], 2),
        )

    def build_trend(self, cases: list[Case], profile: str) -> list[TrendPoint]:
        year_buckets: dict[int, Counter[str]] = defaultdict(Counter)
        for item in cases:
            if item.date_of_judgment is None:
                continue
            year = int(item.date_of_judgment.year)
            year_buckets[year][
                self._normalize_verdict(item.verdict or "", profile)
            ] += 1

        trend_points: list[TrendPoint] = []
        for year in sorted(year_buckets.keys())[-5:]:
            counts = year_buckets[year]
            total = sum(counts.values())
            if total == 0:
                continue
            dominant, dominant_count = counts.most_common(1)[0]
            trend_points.append(
                TrendPoint(
                    year=year,
                    dominant_outcome=dominant,
                    dominant_percentage=round((dominant_count / total) * 100.0, 1),
                )
            )
        return trend_points

    def build_key_factors(self, cases: list[Case], profile: str) -> list[KeyFactor]:
        if not cases:
            return []

        court_counts = Counter([(item.court or "Unknown").strip() for item in cases])
        top_court, top_count = court_counts.most_common(1)[0]
        court_influence = min(30.0, round((top_count / max(1, len(cases))) * 100.0, 1))

        if profile == "constitutional":
            return [
                KeyFactor(
                    name="Procedural due-process context", influence_percent=31.0
                ),
                KeyFactor(name="Rights-restriction scrutiny", influence_percent=26.0),
                KeyFactor(
                    name=f"Forum concentration ({top_court})",
                    influence_percent=court_influence,
                ),
            ]
        if profile in {"criminal", "economic"}:
            return [
                KeyFactor(name="Evidence quality signals", influence_percent=33.0),
                KeyFactor(name="Sections/charges pattern", influence_percent=24.0),
                KeyFactor(
                    name=f"Forum concentration ({top_court})",
                    influence_percent=court_influence,
                ),
            ]
        return [
            KeyFactor(name="Relief maintainability patterns", influence_percent=28.0),
            KeyFactor(name="Documentary support signals", influence_percent=24.0),
            KeyFactor(
                name=f"Forum concentration ({top_court})",
                influence_percent=court_influence,
            ),
        ]

    def build_confidence_band(self, sample_size: int) -> ConfidenceBand:
        if sample_size >= 600:
            return ConfidenceBand(level="high", lower_bound=70.0, upper_bound=88.0)
        if sample_size >= 200:
            return ConfidenceBand(level="medium", lower_bound=58.0, upper_bound=82.0)
        return ConfidenceBand(level="low", lower_bound=45.0, upper_bound=74.0)

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

    def _extract_sentence_years(self, sentence: str | None) -> float | None:
        if not sentence:
            return None
        text = sentence.lower()
        match = re.search(r"(\d+(?:\.\d+)?)\s*(year|years|yr|yrs)", text)
        if not match:
            return None
        try:
            value = float(match.group(1))
        except ValueError:
            return None
        return max(0.0, value)
