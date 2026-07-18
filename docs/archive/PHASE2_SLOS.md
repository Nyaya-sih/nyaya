# Phase 2 SLOs

## Quality SLOs

Quality gates are split by evaluation dataset type.

### A) Heuristic Gold Set (current `data/evals/similar_cases_gold.jsonl`)

- Recall@20 >= 0.40
- nDCG@10 >= 0.37
- Precision@10 >= 0.33
- MRR@10 tracked and non-regressing release-over-release

### B) Human-Judged Gold Set (target for full production sign-off)

- Recall@20 >= 0.75
- nDCG@10 >= 0.60
- Precision@10 >= 0.55
- MRR@10 tracked and non-regressing release-over-release

Measured using: `scripts/17_eval_retrieval_quality.py`

## Performance SLOs

- `POST /api/v1/cases/similar` (warm): p95 <= 3000 ms
- Concurrent default scenario error rate < 1%
- Filter-heavy and long-text scenarios remain within acceptable degradation band

Measured using: `scripts/15_benchmark_search.py`

## Reliability SLOs

- Search endpoint availability >= 99.5%
- Fallback behavior works when reranker fails (degraded mode response)
- Index integrity checker must report pass/warn with explicit drift counts

Measured using:
- `scripts/16_verify_index_integrity.py`
- tests for degraded mode fallback in `tests/test_search_engine.py`

## Release Gate

Phase 2 release requires all of:

- Full test suite green (`pytest tests/`)
- Quality metrics meeting thresholds
- Benchmarks within performance targets
- Index integrity report generated and reviewed
