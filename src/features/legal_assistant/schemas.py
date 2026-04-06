"""Schemas for Legal Research Assistant (Phase 3)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    """Single citation attached to an assistant answer."""

    citation_id: str
    source_type: Literal["case", "statute", "constitution", "document", "other"]
    title: str
    act_or_case: str
    section_or_article: Optional[str] = None
    excerpt: str
    score: float = Field(ge=0.0, le=1.0)


class ConfidenceBreakdown(BaseModel):
    """Confidence summary for assistant answers."""

    overall: float = Field(ge=0.0, le=1.0)
    retrieval_support: float = Field(ge=0.0, le=1.0)
    citation_coverage: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)


class SessionContext(BaseModel):
    """Current active context for a session."""

    source: Literal["none", "upload", "case"] = "none"
    source_ref: Optional[str] = None
    title: Optional[str] = None
    text_preview: Optional[str] = None
    text_length: int = 0


class SessionMessage(BaseModel):
    """Assistant or user message in session history."""

    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class CreateSessionResponse(BaseModel):
    """Response for session creation."""

    session_id: str
    created_at: datetime
    expires_at: datetime
    ttl_minutes: int


class SetContextResponse(BaseModel):
    """Response after session context is set."""

    session_id: str
    context: SessionContext
    warnings: list[str] = Field(default_factory=list)


class AssistantQueryRequest(BaseModel):
    """Query payload for assistant Q&A."""

    session_id: str = Field(min_length=8, max_length=128)
    question: str = Field(min_length=5, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=20)
    include_history: bool = True


class AssistantQueryResponse(BaseModel):
    """Answer payload returned by assistant query endpoint."""

    session_id: str
    answer_text: str
    citations: list[CitationItem] = Field(default_factory=list)
    confidence: ConfidenceBreakdown
    disclaimer: str
    warnings: list[str] = Field(default_factory=list)
    retrieval_mode: Literal["placeholder", "retrieval", "degraded"]
    created_at: datetime


class SessionHistoryResponse(BaseModel):
    """Session history payload."""

    session_id: str
    context: SessionContext
    messages: list[SessionMessage]


class DeleteSessionResponse(BaseModel):
    """Delete session response payload."""

    session_id: str
    deleted: bool
