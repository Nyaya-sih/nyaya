# NyayaAI Project Status (Source of Truth)

Last updated: 2026-04-06
Owner: Engineering

This is the single source of truth for current project phase status and release readiness.

## Executive Status

- Phase 1 (Data Foundation): complete
- Phase 2 (Similar Case Retrieval): engineering-complete; production sign-off pending
- Phase 3 (Legal Research Assistant): not started
- Phase 4 (Simulated Courtroom): not started
- Phase 5 (Outcome Tendency Analyzer): not started
- Phase 6 (Integration and Launch): not started

## What is Done So Far

### Data Foundation (Phase 1)

- Cleaned and validated case corpus loaded into Postgres
- Current dataset report: `data/processed/production_readiness_report.json`
- Report snapshot (latest file):
  - total cases: 10,005
  - non-invalid cases: 9,616
  - average confidence: 0.7657
  - invalid rate: 3.89%

### Similar Case Retrieval (Phase 2)

- Backend retrieval stack implemented:
  - embeddings: `src/features/similar_cases/embedding_generator.py`
  - vector store: `src/features/similar_cases/vector_store.py`
  - search orchestration: `src/features/similar_cases/search_engine.py`
  - reranking: `src/features/similar_cases/reranker.py`
  - explanation layer: `src/features/similar_cases/similarity_analyzer.py`
- API implemented and mounted:
  - router: `src/features/similar_cases/router.py`
  - app entry: `src/api/main.py`
- Frontend implemented for Feature 3:
  - search page: `frontend/src/app/search/page.tsx`
  - results page: `frontend/src/app/results/page.tsx`
  - API integration: `frontend/src/lib/api/search.ts`
- Ops tooling implemented:
  - embeddings build: `scripts/13_generate_embeddings.py`
  - fulltext embeddings: `scripts/14_generate_fulltext_embeddings.py`
  - benchmark: `scripts/15_benchmark_search.py`
  - integrity checker: `scripts/16_verify_index_integrity.py`
  - retrieval eval: `scripts/17_eval_retrieval_quality.py`

## Current Gates (Latest Artifacts)

- Test suite: pass (`96 passed`)
  - command: `PYTHONPATH=. venv/bin/pytest tests/ -q`
- Index integrity: pass
  - report: `data/processed/index_integrity_report.json`
  - combined/factual/legal/fulltext counts match non-invalid db count (delta 0)
- Heuristic retrieval quality: pass for current heuristic gate
  - report: `data/processed/retrieval_eval_report.json`
  - precision@10: 0.3519
  - recall@20: 0.4839
  - mrr@10: 0.5671
  - ndcg@10: 0.4103
- Benchmark (warm p95 target <= 3000 ms): pass
  - report: `data/processed/benchmark_results.json`
  - warm default p95: 2394.1 ms

## Remaining Work Before Phase 2 Production Sign-Off

- Human-judged evaluation is prepared but not completed:
  - packet tooling exists (`scripts/21` to `scripts/25`)
  - source packets exist: `data/evals/similar_cases_human_packets.jsonl`
  - human gold file not generated yet
- Release hardening still needed:
  - CI workflows
  - deployment packaging for backend/frontend
  - stronger monitoring and alerting

## Immediate Next Milestones

1. Start Phase 3 (Legal Research Assistant)
2. Build Phase 4 orchestration scaffold in parallel
3. Execute human-judged eval later (deferred intentionally)

## Document Policy

All older phase-status files under `docs/notes/` are historical snapshots only.
Use this file for current status decisions.
