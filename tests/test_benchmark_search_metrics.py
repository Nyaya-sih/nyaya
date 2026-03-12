"""Tests for benchmark search metrics summarization."""

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "15_benchmark_search.py"
SPEC = importlib.util.spec_from_file_location("benchmark_search", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_summarize_latencies_keys_present():
    """Summary output should contain expected benchmark keys."""
    stats = MODULE._summarize_latencies(
        latencies=[100.0, 120.0, 140.0],
        total_time=1.0,
        errors=0,
        total_requests=3,
    )
    assert "p50_ms" in stats
    assert "p95_ms" in stats
    assert "throughput_rps" in stats
    assert "error_rate" in stats


def test_summarize_latencies_handles_empty():
    """Empty latency list should return safe default zeros."""
    stats = MODULE._summarize_latencies(
        latencies=[],
        total_time=0.0,
        errors=0,
        total_requests=1,
    )
    assert stats["p50_ms"] == 0.0
    assert stats["throughput_rps"] == 0.0
