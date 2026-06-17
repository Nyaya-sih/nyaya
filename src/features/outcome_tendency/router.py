"""FastAPI router for Phase 5 outcome tendency analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_outcome_tendency_service
from src.features.outcome_tendency.schemas import (
    OutcomeTendencyRequest,
    OutcomeTendencyResponse,
)
from src.features.outcome_tendency.service import (
    OutcomeTendencyInputError,
    OutcomeTendencyService,
)


router = APIRouter(prefix="/api/v1/cases", tags=["Outcome Tendency Analyzer"])


@router.post("/tendency", response_model=OutcomeTendencyResponse)
def analyze_tendency(
    payload: OutcomeTendencyRequest,
    tendency_service: OutcomeTendencyService = Depends(get_outcome_tendency_service),
    db_session: Session = Depends(get_db_session),
) -> OutcomeTendencyResponse:
    """Generate historical outcome tendency insights for a case input."""
    try:
        return tendency_service.analyze(payload, db_session=db_session)
    except OutcomeTendencyInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
