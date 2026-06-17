"""Schemas for Phase 5 outcome tendency API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


TendencyMode = Literal["baseline", "ml"]
TendencySourceType = Literal["text", "case_id"]
TendencyStatus = Literal["completed", "insufficient_data"]


class OutcomeTendencyRequest(BaseModel):
    """Request payload for outcome tendency analysis."""

    mode: TendencyMode = "baseline"
    source_type: TendencySourceType = "text"
    case_text: Optional[str] = Field(default=None, max_length=120000)
    case_id: Optional[int] = Field(default=None, ge=1)
    top_k_similar: int = Field(default=300, ge=50, le=2000)
    year_from: Optional[int] = Field(default=None, ge=1950, le=2100)
    year_to: Optional[int] = Field(default=None, ge=1950, le=2100)


class OutcomeBucket(BaseModel):
    """Outcome distribution bucket."""

    label: str
    count: int = Field(ge=0)
    percentage: float = Field(ge=0.0, le=100.0)


class SentenceDistribution(BaseModel):
    """Sentence tendency summary."""

    average_years: float = Field(ge=0.0)
    median_years: float = Field(ge=0.0)
    min_years: float = Field(ge=0.0)
    max_years: float = Field(ge=0.0)


class TrendPoint(BaseModel):
    """Year-over-year tendency point."""

    year: int = Field(ge=1950, le=2100)
    dominant_outcome: str
    dominant_percentage: float = Field(ge=0.0, le=100.0)


class KeyFactor(BaseModel):
    """Primary factor influencing historical tendency."""

    name: str
    influence_percent: float = Field(ge=0.0, le=100.0)


class ExplainabilitySignal(BaseModel):
    """Explainability signal surfaced to users."""

    factor: str
    influence_percent: float = Field(ge=0.0, le=100.0)
    evidence_note: str


class BiasSliceMetric(BaseModel):
    """Slice-level disparity metric."""

    slice_name: str
    dominant_outcome: str
    dominant_rate_percent: float = Field(ge=0.0, le=100.0)
    sample_size: int = Field(ge=0)


class BiasAuditSummary(BaseModel):
    """Bias and disparity summary payload."""

    disparity_flag: bool = False
    drift_flag: bool = False
    max_slice_gap_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    slice_metrics: list[BiasSliceMetric] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConfidenceBand(BaseModel):
    """Confidence context for tendency summary."""

    level: str
    lower_bound: float = Field(ge=0.0, le=100.0)
    upper_bound: float = Field(ge=0.0, le=100.0)
    method: str = "sample_size_heuristic"
    reliability_score: float = Field(default=0.0, ge=0.0, le=1.0)


class OutcomeTendencyResponse(BaseModel):
    """Response payload for outcome tendency analysis."""

    analysis_id: str
    status: TendencyStatus
    created_at: datetime
    summary_text: str
    sample_size: int = Field(ge=0)
    outcome_distribution: list[OutcomeBucket] = Field(default_factory=list)
    sentence_distribution: Optional[SentenceDistribution] = None
    trend_analysis: list[TrendPoint] = Field(default_factory=list)
    key_factors: list[KeyFactor] = Field(default_factory=list)
    explainability_signals: list[ExplainabilitySignal] = Field(default_factory=list)
    confidence_band: ConfidenceBand
    confidence_notes: list[str] = Field(default_factory=list)
    bias_audit: BiasAuditSummary
    cohort_filters: dict[str, str | int | None] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str
    warnings: list[str] = Field(default_factory=list)
