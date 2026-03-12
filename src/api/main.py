"""
FastAPI app entry point for NyayaAI.

Startup: Initialize SimilarCaseSearchEngine and attach to app.state
CORS: Allow http://localhost:3000 (for future Next.js frontend)
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


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Health status payload.
    """
    return {"status": "ok"}
