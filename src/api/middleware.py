"""API middleware utilities."""

import time

from fastapi import Request
from loguru import logger


async def request_logging_middleware(request: Request, call_next):
    """Log request processing time.

    Args:
        request: FastAPI request object.
        call_next: Next middleware/callable.

    Returns:
        Response object.
    """
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=f"{elapsed_ms:.2f}",
    )
    return response
