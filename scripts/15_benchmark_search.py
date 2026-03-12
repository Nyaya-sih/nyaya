"""
Performance benchmark for search API.

Tests:
1. Cold start (first request after server start)
2. Warm requests (100 sequential requests)
3. Concurrent requests (10 simultaneous)

Metrics:
- Latency percentiles (p50, p90, p95, p99)
- Throughput (requests/second)
- Error rate

Report saved to: data/processed/benchmark_results.json

Usage: Run this with the API already running on localhost:8000
"""

import asyncio
import json
import time
from pathlib import Path

import httpx
import numpy as np
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.database.models import Case


API_HOST = settings.api_host if settings.api_host != "0.0.0.0" else "localhost"
API_URL = f"http://{API_HOST}:{settings.api_port}/api/v1/cases/similar"


def main() -> None:
    """Run API performance benchmarks."""
    payload = _build_payload()
    if not payload:
        logger.error("No sample payload available for benchmarking")
        return

    filter_heavy_payload = {
        **payload,
        "top_k": 10,
        "similarity_mode": "combined",
        "court": "High Court of Delhi",
        "case_type": "Criminal",
        "year_from": 2018,
        "year_to": 2025,
    }
    long_text_payload = {
        **payload,
        "top_k": 5,
        "text": (payload.get("text", "") + "\n") * 3,
    }

    results = {
        "cold_start": _run_cold_start(payload),
        "warm_requests_default": _run_warm_requests(payload),
        "warm_requests_filter_heavy": _run_warm_requests(
            filter_heavy_payload, total_requests=50
        ),
        "warm_requests_long_text": _run_warm_requests(
            long_text_payload, total_requests=30
        ),
        "concurrent_requests_default": asyncio.run(
            _run_concurrent_requests(payload, concurrent_requests=10)
        ),
        "concurrent_requests_filter_heavy": asyncio.run(
            _run_concurrent_requests(filter_heavy_payload, concurrent_requests=8)
        ),
    }

    output_path = Path("data/processed/benchmark_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    logger.info("Benchmark results saved", path=str(output_path))


def _build_payload() -> dict:
    """Fetch a sample case for search payload.

    Returns:
        Request payload dictionary.
    """
    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        case = session.query(Case).filter(Case.full_text.isnot(None)).first()
        if not case or not case.full_text:
            return {}
        return {"text": case.full_text[:5000], "top_k": 5}
    finally:
        session.close()


def _run_cold_start(payload: dict) -> dict:
    """Run cold start benchmark.

    Args:
        payload: Search payload.

    Returns:
        Benchmark stats.
    """
    with httpx.Client(timeout=60) as client:
        start = time.time()
        response = client.post(API_URL, json=payload)
        elapsed = (time.time() - start) * 1000

    return {
        "status_code": response.status_code,
        "latency_ms": elapsed,
        "error": response.text if response.status_code != 200 else None,
    }


def _run_warm_requests(payload: dict, total_requests: int = 100) -> dict:
    """Run warm sequential benchmark.

    Args:
        payload: Search payload.

    Returns:
        Benchmark stats.
    """
    latencies = []
    errors = 0

    with httpx.Client(timeout=60) as client:
        start = time.time()
        for _ in range(total_requests):
            request_start = time.time()
            response = client.post(API_URL, json=payload)
            latencies.append((time.time() - request_start) * 1000)
            if response.status_code != 200:
                errors += 1
        total_time = time.time() - start

    return _summarize_latencies(
        latencies, total_time, errors, total_requests=total_requests
    )


async def _run_concurrent_requests(
    payload: dict, concurrent_requests: int = 10
) -> dict:
    """Run concurrent benchmark with 10 simultaneous requests.

    Args:
        payload: Search payload.

    Returns:
        Benchmark stats.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        start = time.time()
        tasks = [_timed_post(client, payload) for _ in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start

    latencies = [result[0] for result in results]
    errors = sum(1 for result in results if result[1] != 200)
    return _summarize_latencies(
        latencies, total_time, errors, total_requests=concurrent_requests
    )


async def _timed_post(client: httpx.AsyncClient, payload: dict) -> tuple[float, int]:
    """Send a timed POST request.

    Args:
        client: HTTPX async client.
        payload: Request payload.

    Returns:
        Tuple of latency and status code.
    """
    start = time.time()
    response = await client.post(API_URL, json=payload)
    return (time.time() - start) * 1000, response.status_code


def _summarize_latencies(
    latencies: list, total_time: float, errors: int, total_requests: int
) -> dict:
    """Summarize latency stats.

    Args:
        latencies: List of latencies in ms.
        total_time: Total time in seconds.
        errors: Error count.
        total_requests: Number of requests.

    Returns:
        Summary dictionary.
    """
    latencies_array = np.array(latencies)
    return {
        "p50_ms": float(np.percentile(latencies_array, 50)) if latencies else 0.0,
        "p90_ms": float(np.percentile(latencies_array, 90)) if latencies else 0.0,
        "p95_ms": float(np.percentile(latencies_array, 95)) if latencies else 0.0,
        "p99_ms": float(np.percentile(latencies_array, 99)) if latencies else 0.0,
        "throughput_rps": float(total_requests / total_time) if total_time > 0 else 0.0,
        "error_rate": float(errors / total_requests),
    }


if __name__ == "__main__":
    main()
