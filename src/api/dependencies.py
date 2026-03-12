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
