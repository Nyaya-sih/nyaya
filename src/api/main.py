"""
FastAPI app entry point for NyayaAI.

Startup: Initialize SimilarCaseSearchEngine and attach to app.state
CORS: Allow local Next.js development origins
Include: similar_cases router
Health: GET /health endpoint
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from openai import OpenAI

from src.config.settings import settings
from src.api.middleware import request_logging_middleware
from src.features.courtroom.router import router as courtroom_router
from src.features.courtroom.service import CourtroomService
from src.features.legal_assistant.router import router as legal_assistant_router
from src.features.legal_assistant.service import LegalAssistantService
from src.features.outcome_tendency.router import router as outcome_tendency_router
from src.features.outcome_tendency.service import OutcomeTendencyService
from src.features.similar_cases.router import router as similar_cases_router
from src.features.similar_cases.search_engine import SimilarCaseSearchEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan to initialize resources.

    Args:
        app: FastAPI app instance.
    """
    logger.info("API startup initialized")
    openai_client = OpenAI(api_key=settings.openai_api_key)
    app.state.search_engine = SimilarCaseSearchEngine(openai_client)
    logger.info("Search engine initialized")
    app.state.assistant_service = LegalAssistantService()
    logger.info("Legal assistant service initialized")
    app.state.courtroom_service = CourtroomService()
    logger.info("Courtroom service initialized")
    app.state.outcome_tendency_service = OutcomeTendencyService()
    logger.info("Outcome tendency service initialized")
    yield
    logger.info("API shutdown completed")


app = FastAPI(title="NyayaAI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_logging_middleware)
app.include_router(similar_cases_router)
app.include_router(outcome_tendency_router)
app.include_router(legal_assistant_router)
app.include_router(courtroom_router)


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Health status payload.
    """
    return {"status": "ok"}
