"""Schemas for Phase 4 simulated courtroom API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


CourtroomMode = Literal["quick", "full"]
CourtroomStatus = Literal[
    "queued",
    "running",
    "completed",
    "degraded",
    "failed",
    "cancelled",
]


CourtroomEventStage = Literal[
    "ingestion",
    "group_deliberation",
    "rebuttal",
    "judicial",
    "verdict",
]

CourtroomEventType = Literal[
    "frame",
    "position",
    "revision",
    "objection",
    "rebuttal",
    "synthesis",
    "vote",
    "verdict",
]


class CourtroomAnalyzeRequest(BaseModel):
    """Input payload for courtroom analysis run."""

    mode: CourtroomMode = "quick"
    include_rebuttal: bool = False
    source_type: Literal["text", "case_id"] = "text"
    case_text: Optional[str] = Field(default=None, max_length=120000)
    case_id: Optional[int] = Field(default=None, ge=1)
    top_k_legal: int = Field(default=8, ge=3, le=25)
    top_k_cases: int = Field(default=6, ge=0, le=20)
    role_model_overrides: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    max_cost_usd: Optional[float] = Field(default=None, ge=0.0)


class Citation(BaseModel):
    """Structured citation reference used throughout courtroom events."""

    doc_id: str
    section_ref: str
    quoted_text: Optional[str] = None


class TrialEvent(BaseModel):
    """Canonical event emitted by the courtroom simulation."""

    model_config = ConfigDict(protected_namespaces=())

    event_id: str
    session_id: str
    stage: CourtroomEventStage
    role: str
    agent_id: str
    model_provider: str
    model_id: str
    round: int
    event_type: CourtroomEventType
    content: str
    responding_to: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime


class GroupSynthesis(BaseModel):
    """Structured output for a role group's final synthesis."""

    role: str
    final_argument: str
    key_evidence_cited: list[Citation] = Field(default_factory=list)
    raw_confidence: float = Field(ge=0.0, le=1.0)
    agreement_ratio: float = Field(ge=0.0, le=1.0)
    weighted_confidence: float = Field(ge=0.0, le=1.0)
    dissent_notes: list[str] = Field(default_factory=list)


class JudgeVote(BaseModel):
    """Single judge panel vote."""

    model_config = ConfigDict(protected_namespaces=())

    agent_id: str
    model_id: str
    position: str
    confidence: float = Field(ge=0.0, le=1.0)
    is_dissent: bool = False


class VerdictRecord(BaseModel):
    """Final courtroom verdict payload."""

    verdict: str
    reasoning: str
    charges_analysis: list[str] = Field(default_factory=list)
    judge_votes: list[JudgeVote] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    procedural_flags: list[str] = Field(default_factory=list)


class CourtroomCriteriaScores(BaseModel):
    """Rubric criteria scores (1-100)."""

    legal_accuracy: float = Field(ge=1.0, le=100.0)
    constitutional_alignment: float = Field(ge=1.0, le=100.0)
    logical_coherence: float = Field(ge=1.0, le=100.0)
    precedent_usage: float = Field(ge=1.0, le=100.0)
    fairness_balance: float = Field(ge=1.0, le=100.0)
    practical_applicability: float = Field(ge=1.0, le=100.0)


class CourtroomRoleAnalysis(BaseModel):
    """Single role analysis output."""

    role_name: str
    analysis_text: str
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    provider: Optional[str] = None
    model: Optional[str] = None
    degraded: bool = False


class CourtroomEvaluationItem(BaseModel):
    """One evaluator's rubric score against one target analysis."""

    evaluator_role: str
    target_role: str
    criteria_scores: CourtroomCriteriaScores
    weighted_score: float = Field(ge=1.0, le=100.0)
    justification: str


class CourtroomSynthesis(BaseModel):
    """Judge-style synthesis payload."""

    executive_summary: str
    recommended_outcome: str
    confidence: float = Field(ge=0.0, le=1.0)
    consensus_points: list[str] = Field(default_factory=list)
    disagreement_points: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    legal_principles_applied: list[str] = Field(default_factory=list)


class CourtroomTransparencyDashboard(BaseModel):
    """Transparency and diagnostics payload."""

    consensus_meter: float = Field(ge=0.0, le=1.0)
    disagreement_index: float = Field(ge=0.0, le=1.0)
    estimated_cost_usd: float = Field(ge=0.0)
    total_runtime_ms: int = Field(ge=0)
    estimated_token_usage: int = Field(default=0, ge=0)
    score_matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    criteria_averages: dict[str, float] = Field(default_factory=dict)
    evaluator_summary: dict[str, dict[str, float | int]] = Field(default_factory=dict)


class CreateCourtroomAnalysisResponse(BaseModel):
    """Response after creating a courtroom analysis."""

    analysis_id: str
    status: CourtroomStatus
    mode: CourtroomMode
    created_at: datetime
    eta_seconds: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class CourtroomAnalysisStatusResponse(BaseModel):
    """Progress status for a courtroom analysis run."""

    analysis_id: str
    status: CourtroomStatus
    stage: str
    progress_percent: int = Field(ge=0, le=100)
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class CourtroomAnalysisResponse(BaseModel):
    """Full courtroom analysis report."""

    analysis_id: str
    status: CourtroomStatus
    mode: CourtroomMode
    created_at: datetime
    completed_at: Optional[datetime] = None
    role_analyses: list[CourtroomRoleAnalysis] = Field(default_factory=list)
    evaluation_breakdown: list[CourtroomEvaluationItem] = Field(default_factory=list)
    rebuttal_enabled: bool = False
    rebuttal_changes: list[str] = Field(default_factory=list)
    synthesis: CourtroomSynthesis
    transparency_dashboard: CourtroomTransparencyDashboard
    trial_events: list[TrialEvent] = Field(default_factory=list)
    disclaimer: str
    warnings: list[str] = Field(default_factory=list)


class CancelCourtroomAnalysisResponse(BaseModel):
    """Cancellation response payload."""

    analysis_id: str
    cancelled: bool
    status: CourtroomStatus
