"""FastAPI router for Phase 3 Legal Research Assistant."""

from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_legal_assistant_service
from src.database.models import Case
from src.features.legal_assistant.schemas import (
    AssistantQueryRequest,
    AssistantQueryResponse,
    CreateSessionResponse,
    DeleteSessionResponse,
    SessionHistoryResponse,
    SetContextResponse,
)
from src.features.legal_assistant.service import (
    LegalAssistantService,
    SessionNotFoundError,
)
from src.utils.document_processor import DocumentProcessor


router = APIRouter(prefix="/api/v1/assistant", tags=["Legal Research Assistant"])


class SetCaseContextRequest(BaseModel):
    """Optional flags for context from existing case."""

    include_full_text: bool = True
    max_chars: int = Field(default=20000, ge=1000, le=120000)


@router.post("/session", response_model=CreateSessionResponse)
def create_session(
    assistant_service: LegalAssistantService = Depends(get_legal_assistant_service),
) -> CreateSessionResponse:
    """Create a new legal assistant session."""
    return assistant_service.create_session()


@router.post("/session/{session_id}/context/upload", response_model=SetContextResponse)
def set_context_from_upload(
    session_id: str,
    file: UploadFile = File(...),
    assistant_service: LegalAssistantService = Depends(get_legal_assistant_service),
) -> SetContextResponse:
    """Set active session context from uploaded file (.pdf/.docx/.txt)."""
    extension = Path(file.filename).suffix.lower() if file.filename else ""
    if extension not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, and TXT files are supported.",
        )

    text = ""
    temp_path = None
    try:
        if extension == ".txt":
            text = file.file.read().decode("utf-8", errors="ignore")
        else:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=extension
            ) as temp_file:
                temp_file.write(file.file.read())
                temp_path = Path(temp_file.name)
            text = DocumentProcessor().extract_text(temp_path)

        if len(text.strip()) < 100:
            raise HTTPException(
                status_code=400,
                detail="Extracted context is too short for assistant analysis.",
            )

        return assistant_service.set_context(
            session_id=session_id,
            source="upload",
            source_ref=file.filename,
            title=file.filename,
            text=text,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.post(
    "/session/{session_id}/context/case/{case_id}",
    response_model=SetContextResponse,
)
def set_context_from_case(
    session_id: str,
    case_id: int,
    options: SetCaseContextRequest,
    assistant_service: LegalAssistantService = Depends(get_legal_assistant_service),
    db_session: Session = Depends(get_db_session),
) -> SetContextResponse:
    """Set active session context from an existing case record."""
    case = db_session.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    context_blocks = [
        case.case_title or "",
        " ".join(case.headnotes or []),
        case.key_arguments_petitioner or "",
        case.key_arguments_respondent or "",
        case.court_reasoning or "",
    ]
    if options.include_full_text and case.full_text:
        context_blocks.append(case.full_text)

    text = "\n\n".join(block for block in context_blocks if block).strip()
    if not text:
        raise HTTPException(
            status_code=400, detail="Case has insufficient textual context."
        )

    text = text[: options.max_chars]
    try:
        return assistant_service.set_context(
            session_id=session_id,
            source="case",
            source_ref=str(case.id),
            title=case.case_title,
            text=text,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/query", response_model=AssistantQueryResponse)
def assistant_query(
    payload: AssistantQueryRequest,
    assistant_service: LegalAssistantService = Depends(get_legal_assistant_service),
) -> AssistantQueryResponse:
    """Run legal assistant query in a session."""
    try:
        return assistant_service.query(
            session_id=payload.session_id,
            question=payload.question,
            top_k=payload.top_k,
            include_history=payload.include_history,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/session/{session_id}/history", response_model=SessionHistoryResponse)
def get_session_history(
    session_id: str,
    assistant_service: LegalAssistantService = Depends(get_legal_assistant_service),
) -> SessionHistoryResponse:
    """Get session conversation history and active context."""
    try:
        return assistant_service.get_history(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/session/{session_id}", response_model=DeleteSessionResponse)
def delete_session(
    session_id: str,
    assistant_service: LegalAssistantService = Depends(get_legal_assistant_service),
) -> DeleteSessionResponse:
    """Delete assistant session."""
    deleted = assistant_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return DeleteSessionResponse(session_id=session_id, deleted=True)
