"""
FastAPI shared dependencies.

get_search_engine(): Returns app.state.search_engine
  - Use Request object to access app.state
  - Raise 503 if search engine not initialized

get_db_session(): Yields SQLAlchemy session, closes in finally
"""

from typing import Generator

from fastapi import Request, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.config.settings import settings


def get_search_engine(request: Request):
    """Return initialized search engine from app state.

    Args:
        request: FastAPI request object.

    Returns:
        SimilarCaseSearchEngine instance.
    """
    search_engine = getattr(request.app.state, "search_engine", None)
    if not search_engine:
        raise HTTPException(status_code=503, detail="Search engine not initialized.")
    return search_engine


def get_db_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session.

    Yields:
        SQLAlchemy Session instance.
    """
    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


def get_legal_assistant_service(request: Request):
    """Return initialized legal assistant service from app state."""
    assistant_service = getattr(request.app.state, "assistant_service", None)
    if not assistant_service:
        raise HTTPException(
            status_code=503,
            detail="Legal assistant service not initialized.",
        )
    return assistant_service


def get_courtroom_service(request: Request):
    """Return initialized courtroom service from app state."""
    courtroom_service = getattr(request.app.state, "courtroom_service", None)
    if not courtroom_service:
        raise HTTPException(
            status_code=503,
            detail="Courtroom service not initialized.",
        )
    return courtroom_service


def get_outcome_tendency_service(request: Request):
    """Return initialized outcome tendency service from app state."""
    tendency_service = getattr(request.app.state, "outcome_tendency_service", None)
    if not tendency_service:
        raise HTTPException(
            status_code=503,
            detail="Outcome tendency service not initialized.",
        )
    return tendency_service
