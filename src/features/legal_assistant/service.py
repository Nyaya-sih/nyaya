"""Application service for Legal Research Assistant."""

from datetime import datetime, timezone
from typing import Optional

from src.config.settings import settings
from src.features.legal_assistant.answer_generator import AnswerGenerator
from src.features.legal_assistant.citation_validator import CitationValidator
from src.features.legal_assistant.confidence import ConfidenceEstimator
from src.features.legal_assistant.context_builder import ContextBuilder
from src.features.legal_assistant.query_parser import QueryParser
from src.features.legal_assistant.retriever import AssistantRetriever, EvidenceChunk
from src.features.legal_assistant.schemas import (
    AssistantQueryResponse,
    CitationItem,
    CreateSessionResponse,
    SessionContext,
    SessionHistoryResponse,
    SessionMessage,
    SetContextResponse,
)
from src.features.legal_assistant.session_store import InMemorySessionStore


class SessionNotFoundError(Exception):
    """Raised when a session is missing or expired."""


class LegalAssistantService:
    """Coordinates session management and assistant responses."""

    DISCLAIMER = (
        "NyayaAI is a legal decision support tool. This response is not legal advice "
        "and must be reviewed by a qualified legal professional."
    )

    def __init__(self):
        self.store = InMemorySessionStore(
            ttl_minutes=settings.assistant_session_ttl_minutes,
            max_turns=settings.assistant_max_turns,
        )
        self.query_parser = QueryParser()
        self.retriever = AssistantRetriever()
        self.context_builder = ContextBuilder()
        self.answer_generator = AnswerGenerator()
        self.citation_validator = CitationValidator()
        self.confidence_estimator = ConfidenceEstimator()

    def create_session(self) -> CreateSessionResponse:
        """Create assistant session."""
        session = self.store.create_session()
        return CreateSessionResponse(
            session_id=session.session_id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            ttl_minutes=settings.assistant_session_ttl_minutes,
        )

    def set_context(
        self,
        session_id: str,
        source: str,
        source_ref: Optional[str],
        title: Optional[str],
        text: str,
    ) -> SetContextResponse:
        """Set active session context text."""
        session = self._get_required_session(session_id)

        bounded_text = text[: settings.assistant_max_context_chars].strip()
        warnings: list[str] = []
        if len(text) > settings.assistant_max_context_chars:
            warnings.append("Context was truncated to configured storage limit.")

        updated = self.store.update_context(
            session_id=session.session_id,
            source=source,
            source_ref=source_ref,
            title=title,
            text=bounded_text,
        )
        if updated is None:
            raise SessionNotFoundError("Session not found")

        return SetContextResponse(
            session_id=session_id,
            context=self._build_context(updated),
            warnings=warnings,
        )

    def query(
        self,
        session_id: str,
        question: str,
        top_k: int,
        include_history: bool,
    ) -> AssistantQueryResponse:
        """Answer a legal query for an active session."""
        session = self._get_required_session(session_id)

        normalized_question = question.strip()
        if len(normalized_question) > settings.assistant_max_question_chars:
            normalized_question = normalized_question[
                : settings.assistant_max_question_chars
            ]

        parsed = self.query_parser.parse(normalized_question)
        has_context = bool(session.context_text.strip())

        evidence = self.retriever.retrieve(
            question=parsed.normalized_question,
            context_text=session.context_text,
            top_k=top_k,
            statutes_hint=parsed.statutes_hint,
            sections_hint=parsed.sections_hint,
        )
        valid_evidence, citation_warnings = self.citation_validator.validate(evidence)

        # Convert internal chunk ids to stable user-facing citation labels.
        labeled_evidence: list[EvidenceChunk] = []
        for idx, item in enumerate(valid_evidence, start=1):
            labeled_evidence.append(
                EvidenceChunk(
                    citation_id=f"CIT-{idx}",
                    source_type=item.source_type,
                    title=item.title,
                    act_or_case=item.act_or_case,
                    section_or_article=item.section_or_article,
                    excerpt=item.excerpt,
                    score=item.score,
                )
            )

        built_context = self.context_builder.build(
            question=parsed.normalized_question,
            evidence=labeled_evidence,
            max_chars=8000,
        )
        answer_text = self.answer_generator.generate(
            question=parsed.normalized_question,
            built_context=built_context,
            has_context=has_context,
            evidence=labeled_evidence,
        )

        self.store.append_message(
            session_id=session_id, role="user", content=normalized_question
        )
        self.store.append_message(
            session_id=session_id, role="assistant", content=answer_text
        )

        citations = [
            CitationItem(
                citation_id=item.citation_id,
                source_type=item.source_type,
                title=item.title,
                act_or_case=item.act_or_case,
                section_or_article=item.section_or_article,
                excerpt=item.excerpt,
                score=item.score,
            )
            for item in labeled_evidence
        ]
        avg_score = (
            sum(item.score for item in citations) / len(citations) if citations else 0.0
        )
        confidence = self.confidence_estimator.estimate(
            citation_count=len(citations),
            has_context=has_context,
            avg_citation_score=avg_score,
        )

        warnings = list(citation_warnings)
        if not include_history:
            warnings.append("History inclusion disabled for this request.")
        if parsed.statutes_hint:
            warnings.append(
                "Statute hints detected: " + ", ".join(parsed.statutes_hint)
            )

        return AssistantQueryResponse(
            session_id=session_id,
            answer_text=answer_text,
            citations=citations,
            confidence=confidence,
            disclaimer=self.DISCLAIMER,
            warnings=warnings,
            retrieval_mode="retrieval" if citations else "degraded",
            created_at=datetime.now(timezone.utc),
        )

    def get_history(self, session_id: str) -> SessionHistoryResponse:
        """Return bounded session history."""
        session = self._get_required_session(session_id)
        messages = [
            SessionMessage(
                role=turn.role, content=turn.content, created_at=turn.created_at
            )
            for turn in session.messages
        ]
        return SessionHistoryResponse(
            session_id=session_id,
            context=self._build_context(session),
            messages=messages,
        )

    def delete_session(self, session_id: str) -> bool:
        """Delete session data."""
        return self.store.delete_session(session_id)

    def _get_required_session(self, session_id: str):
        session = self.store.get_session(session_id)
        if session is None:
            raise SessionNotFoundError("Session not found or expired")
        return session

    def _build_context(self, session) -> SessionContext:
        preview = session.context_text[:280] if session.context_text else None
        return SessionContext(
            source=session.context_source,
            source_ref=session.context_source_ref,
            title=session.context_title,
            text_preview=preview,
            text_length=len(session.context_text),
        )
