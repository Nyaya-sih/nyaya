"""
FastAPI router for Feature 3: Similar Case Retrieval

Endpoints:
  POST /api/v1/cases/similar          - Search by text
  POST /api/v1/cases/similar/upload   - Search by PDF/DOCX upload
  GET  /api/v1/cases/{case_id}        - Get full case details
  GET  /api/v1/cases/{case_id}/similar - Find similar to existing case
  POST /api/v1/cases/explain          - On-demand LLM explanation
  GET  /api/v1/cases/search/filters   - Get filter options for UI dropdowns
"""

from pathlib import Path
import tempfile
from typing import Optional, Literal

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.api.dependencies import get_search_engine, get_db_session
from src.database.models import Case
from src.features.similar_cases.search_engine import (
    SimilarCaseSearchEngine,
    SearchFilters,
)
from src.utils.document_processor import DocumentProcessor


router = APIRouter(prefix="/api/v1/cases", tags=["Similar Case Retrieval"])


class TextSearchRequest(BaseModel):
    """Search request payload for text search."""

    text: str = Field(..., min_length=100)
    court: Optional[str] = None
    case_type: Optional[str] = None
    year_from: Optional[int] = Field(None, ge=1950, le=2025)
    year_to: Optional[int] = Field(None, ge=1950, le=2025)
    verdict: Optional[str] = None
    top_k: int = Field(settings.default_top_k, ge=1, le=20)
    similarity_mode: Literal["combined", "factual", "legal", "fulltext"] = Field(
        "combined"
    )


class SimilarityDimensionResponse(BaseModel):
    """Similarity dimension response."""

    name: str
    score: float
    reason: str


class SimilarCaseResponse(BaseModel):
    """Response schema for a similar case result."""

    rank: int
    case_id: int
    case_title: str
    court: str
    date_of_judgment: str
    case_type: str
    verdict: str
    combined_score: float
    similarity_explanation: str
    common_statutes: list[str]
    statutes_cited: list[str]
    sections_invoked: list[str]
    dimensions: list[SimilarityDimensionResponse]


class SearchResponse(BaseModel):
    """Search response schema."""

    query_summary: str
    total_results: int
    search_time_ms: float
    results: list[SimilarCaseResponse]
    filters_applied: dict
    disclaimer: str
    retrieval_mode: str
    warnings: list[str] = Field(default_factory=list)


class ExplainRequest(BaseModel):
    """Request schema for on-demand LLM explanation."""

    query_text: str
    case_id: int


@router.post("/similar", response_model=SearchResponse)
def search_similar_cases(
    request: TextSearchRequest,
    search_engine: SimilarCaseSearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """Search for similar cases using plain text.

    Args:
        request: Text search request.
        search_engine: Similar case search engine.

    Returns:
        SearchResponse payload.
    """
    filters = SearchFilters(
        court=request.court,
        case_type=request.case_type,
        year_from=request.year_from,
        year_to=request.year_to,
        verdict=request.verdict,
        similarity_mode=request.similarity_mode,
    )

    response = search_engine.search(request.text, filters=filters, top_k=request.top_k)
    return _convert_search_response(response)


@router.post("/similar/upload", response_model=SearchResponse)
def search_similar_cases_upload(
    file: UploadFile = File(...),
    court: Optional[str] = Form(None),
    case_type: Optional[str] = Form(None),
    year_from: Optional[int] = Form(None, ge=1950, le=2025),
    year_to: Optional[int] = Form(None, ge=1950, le=2025),
    verdict: Optional[str] = Form(None),
    top_k: int = Form(settings.default_top_k, ge=1, le=20),
    similarity_mode: Literal["combined", "factual", "legal", "fulltext"] = Form(
        "combined"
    ),
    search_engine: SimilarCaseSearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """Search for similar cases using uploaded PDF or DOCX.

    Args:
        file: Uploaded PDF/DOCX file.
        court: Court filter.
        case_type: Case type filter.
        year_from: Minimum year.
        year_to: Maximum year.
        verdict: Verdict filter.
        top_k: Result count.
        similarity_mode: Similarity mode.
        search_engine: Similar case search engine.

    Returns:
        SearchResponse payload.
    """
    extension = Path(file.filename).suffix.lower() if file.filename else ""
    if extension not in {".pdf", ".docx"}:
        raise HTTPException(
            status_code=400, detail="Only PDF and DOCX files are supported."
        )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            temp_file.write(file.file.read())
            temp_path = Path(temp_file.name)

        processor = DocumentProcessor()
        extracted_text = processor.extract_text(temp_path)
        if len(extracted_text.strip()) < 100:
            raise HTTPException(
                status_code=400, detail="Extracted text is too short for search."
            )

        filters = SearchFilters(
            court=court,
            case_type=case_type,
            year_from=year_from,
            year_to=year_to,
            verdict=verdict,
            similarity_mode=similarity_mode,
        )
        response = search_engine.search(extracted_text, filters=filters, top_k=top_k)
        return _convert_search_response(response)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Upload search failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail="Failed to process uploaded document."
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.get("/{case_id}")
def get_case_details(
    case_id: int, db_session: Session = Depends(get_db_session)
) -> dict:
    """Get full case details by ID.

    Args:
        case_id: Case ID.
        db_session: Database session.

    Returns:
        Case details payload.
    """
    case = db_session.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    return {
        "case_id": case.id,
        "case_title": case.case_title,
        "court": case.court,
        "date_of_judgment": case.date_of_judgment.isoformat()
        if case.date_of_judgment
        else None,
        "case_type": case.case_type,
        "verdict": case.verdict,
        "statutes_cited": _get_statute_names(case),
        "sections_invoked": case.sections_invoked or [],
        "charges": case.charges or [],
        "key_arguments_petitioner": case.key_arguments_petitioner,
        "key_arguments_respondent": case.key_arguments_respondent,
        "court_reasoning": case.court_reasoning,
        "precedents_cited": [
            {
                "case_name": p.case_name,
                "citation": p.citation,
                "year": p.year,
                "court": p.court,
                "legal_principle": p.legal_principle,
            }
            for p in case.precedents or []
        ],
        "headnotes": case.headnotes or [],
        "full_text": case.full_text,
        "average_confidence": case.average_confidence,
        "validation_status": case.validation_status,
    }


@router.get("/{case_id}/similar", response_model=SearchResponse)
def get_similar_to_case(
    case_id: int,
    top_k: int = Query(settings.default_top_k, ge=1, le=20),
    similarity_mode: Literal["combined", "factual", "legal", "fulltext"] = Query(
        "combined"
    ),
    search_engine: SimilarCaseSearchEngine = Depends(get_search_engine),
    db_session: Session = Depends(get_db_session),
) -> SearchResponse:
    """Find similar cases to an existing case.

    Args:
        case_id: Case ID.
        top_k: Result count.
        similarity_mode: Similarity mode.
        search_engine: Similar case search engine.
        db_session: Database session.

    Returns:
        SearchResponse payload.
    """
    case = db_session.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    query_text = "\n".join(
        [
            case.case_title or "",
            case.key_arguments_petitioner or "",
            case.key_arguments_respondent or "",
            case.court_reasoning or "",
        ]
    ).strip()

    if len(query_text) < 100:
        raise HTTPException(
            status_code=400, detail="Insufficient case text for similarity search."
        )

    filters = SearchFilters(similarity_mode=similarity_mode)
    response = search_engine.search(
        query_text, filters=filters, top_k=top_k, exclude_case_id=case_id
    )
    return _convert_search_response(response)


@router.post("/explain")
def explain_similarity(
    request: ExplainRequest,
    search_engine: SimilarCaseSearchEngine = Depends(get_search_engine),
    db_session: Session = Depends(get_db_session),
) -> dict:
    """Generate LLM explanation for a query and candidate case.

    Args:
        request: ExplainRequest payload.
        search_engine: Similar case search engine.
        db_session: Database session.

    Returns:
        Explanation payload.
    """
    if not settings.enable_llm_explanation:
        raise HTTPException(status_code=403, detail="LLM explanations are disabled.")
    case = db_session.query(Case).filter(Case.id == request.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    payload = {
        "case_title": case.case_title,
        "court": case.court,
        "case_type": case.case_type,
        "verdict": case.verdict,
        "statutes_cited": _get_statute_names(case),
        "sections_invoked": case.sections_invoked or [],
    }
    explanation = search_engine.similarity_analyzer.generate_llm_explanation(
        query_case_text=request.query_text,
        candidate_payload=payload,
        similarity_score=1.0,
    )
    return {"explanation": explanation}


@router.get("/search/filters")
def get_search_filters(db_session: Session = Depends(get_db_session)) -> dict:
    """Get filter options for UI dropdowns.

    Args:
        db_session: Database session.

    Returns:
        Dictionary with filter options.
    """
    courts = sorted(
        {row[0] for row in db_session.query(Case.court).distinct().all() if row[0]}
    )
    case_types = sorted(
        {row[0] for row in db_session.query(Case.case_type).distinct().all() if row[0]}
    )
    verdicts = sorted(
        {row[0] for row in db_session.query(Case.verdict).distinct().all() if row[0]}
    )

    years = [
        row[0].year
        for row in db_session.query(Case.date_of_judgment).distinct().all()
        if row[0]
    ]
    year_range = {
        "min": min(years) if years else None,
        "max": max(years) if years else None,
    }

    return {
        "courts": courts,
        "case_types": case_types,
        "verdicts": verdicts,
        "similarity_modes": ["combined", "factual", "legal", "fulltext"],
        "year_range": year_range,
    }


def _convert_search_response(response) -> SearchResponse:
    """Convert internal response to API response model.

    Args:
        response: Internal SearchResponse object.

    Returns:
        API SearchResponse model.
    """
    results = []
    for item in response.results:
        results.append(
            SimilarCaseResponse(
                rank=item.rank,
                case_id=item.case_id,
                case_title=item.case_title,
                court=item.court,
                date_of_judgment=item.date_of_judgment,
                case_type=item.case_type,
                verdict=item.verdict,
                combined_score=item.combined_score,
                similarity_explanation=item.similarity_explanation.short_explanation,
                common_statutes=item.similarity_explanation.common_statutes,
                statutes_cited=item.statutes_cited,
                sections_invoked=item.sections_invoked,
                dimensions=[
                    SimilarityDimensionResponse(
                        name=dimension.name,
                        score=dimension.score,
                        reason=dimension.reason,
                    )
                    for dimension in item.similarity_explanation.dimensions
                ],
            )
        )

    return SearchResponse(
        query_summary=response.query_summary,
        total_results=response.total_results,
        search_time_ms=response.search_time_ms,
        results=results,
        filters_applied=response.filters_applied,
        disclaimer=response.disclaimer,
        retrieval_mode=getattr(response, "retrieval_mode", "full"),
        warnings=list(getattr(response, "warnings", []) or []),
    )


def _get_statute_names(case: Case) -> list[str]:
    """Extract statute names from case relationships."""
    statutes = []
    for statute in getattr(case, "statutes", []) or []:
        name = getattr(statute, "statute_name", None)
        if name:
            statutes.append(name)
    return statutes
