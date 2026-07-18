# Phase 2 Runbook

## Core Commands

- Full embedding index build:
  - `python scripts/13_generate_embeddings.py`
- Full-text-lite index build:
  - `python scripts/14_generate_fulltext_embeddings.py`
- Integrity verification:
  - `python scripts/16_verify_index_integrity.py`
- Retrieval quality evaluation:
  - `python scripts/17_eval_retrieval_quality.py`
- Performance benchmark:
  - `python scripts/15_benchmark_search.py`

## Daily Health Checks

1. API health:
   - `curl http://localhost:8000/health`
2. Collection counts:
   - Run `scripts/16_verify_index_integrity.py`
3. Recent regression tests:
   - `pytest tests/test_retrieval_regression.py -v`

## Incident: Reranker Failure

Symptoms:
- Search still returns results but with `retrieval_mode=degraded`
- `warnings` contains reranker fallback message

Actions:
1. Verify model package/environment.
2. Keep service running in degraded mode to avoid downtime.
3. Re-run targeted tests:
   - `pytest tests/test_search_engine.py -k reranker -v`

## Incident: Index Drift

Symptoms:
- `index_integrity_report.json` has non-zero drift checks.

Actions:
1. Identify drift direction (DB > Qdrant or Qdrant > DB).
2. Re-run embedding scripts for incremental correction.
3. Re-run integrity checker until stable.

## Release Checklist

1. `pytest tests/ -v`
2. `python scripts/16_verify_index_integrity.py`
3. `python scripts/17_eval_retrieval_quality.py`
4. `python scripts/15_benchmark_search.py`
5. Review generated reports in `data/processed/`
