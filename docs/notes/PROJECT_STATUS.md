# NyayaAI Project Status (Source of Truth)

Last updated: 2026-04-08
Owner: Engineering

This is the single source of truth for current project phase status and release readiness.

## Executive Status

- Phase 1 (Data Foundation): complete
- Phase 2 (Similar Case Retrieval): engineering-complete; production sign-off pending
- Phase 3 (Legal Research Assistant): complete
- Phase 4 (Simulated Courtroom): engineering-complete; production sign-off pending
- Phase 5 (Outcome Tendency Analyzer): complete
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

### Legal Research Assistant (Phase 3)

- Backend assistant stack implemented and mounted:
  - router: `src/features/legal_assistant/router.py`
  - service: `src/features/legal_assistant/service.py`
  - retriever: `src/features/legal_assistant/retriever.py`
  - answer generator + citation validator + confidence: `src/features/legal_assistant/*`
- Session/context features implemented:
  - create/delete sessions
  - context upload from file
  - context attach from existing case
  - history-aware querying
- Legal KB corpus and vector assets produced:
  - chunk corpus under `legal_kb/chunks/`
  - per-act embeddings under `legal_kb/embeddings/`
  - FAISS index + lookup maps under `legal_kb/faiss/`
- Corpus includes broad Indian legal materials:
  - Constitution, BNS/BNSS/BSA, IPC/CrPC/Evidence, CPC, Companies/IT/Consumer/MVA/POCSO/etc.,
    procedural rules, curated Law Commission reports, and legal maxims glossary.
- Frontend assistant interface delivered:
  - page: `frontend/src/app/assistant/page.tsx`
  - client integration: `frontend/src/lib/api/assistant.ts`, `frontend/src/lib/hooks/use-assistant.ts`
- Assistant response quality tuning delivered:
  - LLM-backed legal drafting style with citation-constrained generation
  - user-facing numbered citation labels (`CIT-1`, `CIT-2`, ...) replacing internal chunk ids
- Phase 3 evaluation harness added:
  - `scripts/33_eval_assistant_quality.py`
  - latest report: `data/processed/assistant_eval_report.json`

### Simulated Courtroom (Phase 4)

- Backend courtroom stack implemented and mounted:
  - router: `src/features/courtroom/router.py`
  - service + orchestration: `src/features/courtroom/service.py`, `src/features/courtroom/orchestrator.py`
  - role/eval/rebuttal/synthesis engines: `src/features/courtroom/*_engine.py`
- Contracts and run lifecycle delivered:
  - endpoints under `/api/v1/courtroom/*`
  - in-memory run store with status lifecycle + deterministic run-key cache
  - graceful degraded responses for partial role/provider failures
- Retrieval and scoring transparency delivered:
  - role-aware legal evidence retrieval via `src/features/courtroom/retrieval_adapter.py`
  - anonymous peer evaluation matrix + criteria averages + evaluator summaries
  - transparency payload includes estimated token usage and cost estimation
- Frontend courtroom workflow delivered:
  - page: `frontend/src/app/courtroom/page.tsx`
  - API/hooks: `frontend/src/lib/api/courtroom.ts`, `frontend/src/lib/hooks/use-courtroom.ts`
  - navbar route enabled for `/courtroom`
- Phase 4 evaluation harness added:
  - `scripts/39_eval_courtroom_quality.py`
  - latest report: `data/processed/courtroom_eval_report.json`

### Outcome Tendency Analyzer (Phase 5)

- Iteration 0 scaffolding delivered:
  - router: `src/features/outcome_tendency/router.py`
  - service: `src/features/outcome_tendency/service.py`
  - schemas: `src/features/outcome_tendency/schemas.py`
  - endpoint: `POST /api/v1/cases/tendency`
- Iteration 1 baseline hardening delivered:
  - DB-backed cohort selection: `src/features/outcome_tendency/cohort_selector.py`
  - statistical computation engine: `src/features/outcome_tendency/stats_engine.py`
  - automatic fallback to heuristic tendency when cohort query is unavailable
- Iteration 2 benchmark track started:
  - feature extraction: `src/features/outcome_tendency/feature_builder.py`
  - model benchmarks: `src/features/outcome_tendency/model_runner.py`
  - benchmark script: `scripts/40_benchmark_tendency_models.py`
  - latest report: `data/processed/tendency_benchmark_report.json`
- Iteration 3 confidence calibration delivered:
  - calibration engine: `src/features/outcome_tendency/calibration.py`
  - confidence payload includes method/reliability metadata and confidence notes
- Iteration 4 explainability + bias audit delivered:
  - explainability signals: `src/features/outcome_tendency/explainability.py`
  - slice-level disparity/drift audit: `src/features/outcome_tendency/bias_audit.py`
  - response now includes `explainability_signals` and `bias_audit`
- Iteration 5 frontend dashboard baseline delivered:
  - page: `frontend/src/app/tendency/page.tsx`
  - API client: `frontend/src/lib/api/tendency.ts`
  - hook: `frontend/src/lib/hooks/use-tendency.ts`
  - shared API types expanded in `frontend/src/lib/api/types.ts`
  - navbar route enabled for `/tendency`
- Iteration 6 hardening/docs delivered:
  - eval harness: `scripts/41_eval_tendency_quality.py`
  - runbook: `docs/notes/PHASE5_RUNBOOK.md`
  - release checklist: `docs/notes/PHASE5_RELEASE_CHECKLIST.md`
  - latest eval artifact: `data/processed/tendency_eval_report.json`
- Final sign-off pass executed:
  - benchmark refreshed: `data/processed/tendency_benchmark_report.json`
  - eval refreshed: `data/processed/tendency_eval_report.json`
  - release checklist status tracked in `docs/notes/PHASE5_RELEASE_CHECKLIST.md`
  - drift sensitivity tuned in `src/features/outcome_tendency/bias_audit.py`
  - current eval snapshot: drift_flag_rate `0.0` (threshold met)

## Current Gates (Latest Artifacts)

- Test suite: pass (`96 passed`)
  - command: `PYTHONPATH=. venv/bin/pytest tests/ -q`
- Latest backend suite after Phase 5 Iteration 4: pass (`124 passed`)
  - command: `PYTHONPATH=. ../venv/bin/pytest tests/ -q`
- Frontend lint: pass
  - command: `npm run lint` (from `frontend/`)
- Tendency benchmark report: generated
  - report: `data/processed/tendency_benchmark_report.json`
- Tendency eval report: generated
  - report: `data/processed/tendency_eval_report.json`
  - current snapshot: completion_rate `1.0`, avg_confidence_reliability `0.473`, drift_flag_rate `0.0`
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

1. Start Phase 6 integration and launch plan
2. Harden courtroom online monitoring and live-provider reliability tracking
3. Execute human-judged eval later (deferred intentionally)

## Document Policy

All older phase-status files under `docs/notes/` are historical snapshots only.
Use this file for current status decisions.
