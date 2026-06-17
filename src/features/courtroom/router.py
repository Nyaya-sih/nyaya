"""FastAPI router for Phase 4 simulated courtroom."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_courtroom_service
from src.features.courtroom.schemas import (
    CancelCourtroomAnalysisResponse,
    CourtroomAnalysisResponse,
    CourtroomAnalysisStatusResponse,
    CourtroomAnalyzeRequest,
    CreateCourtroomAnalysisResponse,
)
from src.features.courtroom.service import CourtroomRunNotFoundError, CourtroomService


router = APIRouter(prefix="/api/v1/courtroom", tags=["Simulated Courtroom"])


@router.post("/analyze", response_model=CreateCourtroomAnalysisResponse)
def analyze_case(
    payload: CourtroomAnalyzeRequest,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CreateCourtroomAnalysisResponse:
    """Start a simulated courtroom analysis run."""
    return courtroom_service.create_analysis(payload)


@router.get("/analysis/{analysis_id}", response_model=CourtroomAnalysisResponse)
def get_analysis(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CourtroomAnalysisResponse:
    """Get full courtroom report by analysis id."""
    try:
        return courtroom_service.get_analysis(analysis_id)
    except CourtroomRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/analysis/{analysis_id}/status",
    response_model=CourtroomAnalysisStatusResponse,
)
def get_analysis_status(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CourtroomAnalysisStatusResponse:
    """Get status/progress for courtroom run."""
    try:
        return courtroom_service.get_status(analysis_id)
    except CourtroomRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/analysis/{analysis_id}/cancel",
    response_model=CancelCourtroomAnalysisResponse,
)
def cancel_analysis(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CancelCourtroomAnalysisResponse:
    """Cancel a running courtroom analysis if possible."""
    try:
        return courtroom_service.cancel_analysis(analysis_id)
    except CourtroomRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
