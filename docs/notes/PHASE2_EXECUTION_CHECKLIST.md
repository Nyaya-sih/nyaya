# Phase 2 Execution Checklist (Similar Case Retrieval Hardening)

This checklist is for finishing Phase 2 to production quality using the current repository layout.

## Success Definition (All Required)

- Retrieval quality metrics pass on judged evaluation set.
- API contracts are stable and tested.
- Indexing is reproducible, incremental, and integrity-checked.
- Explanations are evidence-grounded.
- Frontend behavior matches backend filter/scoring semantics.
- Performance SLOs pass.
- Full test suite passes.

## Day 1 - Freeze Scoring Policy

### Tasks

- Freeze scoring equation and tie-break rules in:
  - `src/features/similar_cases/search_engine.py`
  - `src/features/similar_cases/reranker.py`
- Ensure all scoring knobs are in `src/config/settings.py`.
- Add policy document section (or update this file) with final equation.

### Commands

```bash
pytest tests/test_search_engine.py tests/test_reranker.py -v
```

### Acceptance

- Same input query produces stable ordering across repeated runs.
- No hardcoded hidden scoring constants outside settings.

## Day 2 - Filter Semantics Audit

### Tasks

- Verify filter pushdown to vector search in:
  - `src/features/similar_cases/vector_store.py`
- Confirm support for court/date/case_type/verdict/statute filters.
- Confirm `exclude_case_id` works on all paths.
- Add/expand integration tests.

### Commands

```bash
pytest tests/test_vector_store.py tests/test_search_engine.py -v
```

### Acceptance

- Filter behavior in tests matches API docs exactly.

## Day 3 - Explainability Grounding

### Tasks

- Harden explanation generation in:
  - `src/features/similar_cases/similarity_analyzer.py`
- Ensure explanations only claim evidence present in result metadata/text.
- Add tests for explanation grounding.

### Commands

```bash
pytest tests/test_search_engine.py -v
```

### Acceptance

- No explanation field references missing statutes/sections/facts.

## Day 4 - API Contract Lock

### Tasks

- Lock schema and validation in:
  - `src/features/similar_cases/router.py`
  - `src/api/main.py`
- Standardize error format and validation failures.
- Add API contract tests.

### Commands

```bash
pytest tests/ -k "api or search" -v
```

### Acceptance

- No contract drift for request/response fields across reruns.

## Day 5 - Regression Snapshot Suite

### Tasks

- Create fixed query snapshot set and expected rank windows.
- Add regression tests for ranking drift.

### Commands

```bash
pytest tests/ -k "regression or search" -v
```

### Acceptance

- Unexpected ranking drift fails tests.

## Day 6 - Index Integrity Tooling

### Tasks

- Add script: `scripts/16_verify_index_integrity.py`
- Validate DB case count vs Qdrant points vs embedding manifest.
- Add smoke test for integrity checker.

### Commands

```bash
python scripts/16_verify_index_integrity.py
pytest tests/ -k "integrity" -v
```

### Acceptance

- Integrity check returns pass with explicit counts and drift=0 (or justified delta).

## Day 7 - Incremental Indexing

### Tasks

- Extend:
  - `scripts/13_generate_embeddings.py`
  - `scripts/14_generate_fulltext_embeddings.py`
- Add incremental mode, retry queue, resumability.

### Commands

```bash
python scripts/13_generate_embeddings.py
python scripts/14_generate_fulltext_embeddings.py
```

### Acceptance

- Re-run after no changes performs near-zero new upserts.

## Day 8 - Build Gold Evaluation Set

### Tasks

- Create judged set file: `data/evals/similar_cases_gold.jsonl`.
- Include query case, relevant case ids, optional graded relevance.

### Acceptance

- At least 200 judged query cases (recommended 300+).

## Day 9 - Quality Evaluation Harness

### Tasks

- Add script: `scripts/17_eval_retrieval_quality.py`.
- Compute and store:
  - Recall@20
  - Precision@10
  - nDCG@10
  - MRR@10
- Save report to `data/processed/retrieval_eval_report.json`.

### Commands

```bash
python scripts/17_eval_retrieval_quality.py
```

### Acceptance

- Metrics report is generated and deterministic with fixed seed/data.

## Day 10 - Tune and Freeze Retrieval Weights

### Tasks

- Tune weights and rerank blend using eval script.
- Freeze tuned values in `src/config/settings.py`.
- Re-run full eval.

### Commands

```bash
python scripts/17_eval_retrieval_quality.py
pytest tests/test_search_engine.py tests/test_reranker.py -v
```

### Acceptance (Suggested)

- Heuristic set gate (current): Recall@20 >= 0.40, nDCG@10 >= 0.37, Precision@10 >= 0.33
- Human-judged gate (target): Recall@20 >= 0.75, nDCG@10 >= 0.60, Precision@10 >= 0.55

## Day 11 - Performance Benchmark Expansion

### Tasks

- Extend `scripts/15_benchmark_search.py` with filter-heavy and long-query scenarios.
- Capture p50/p90/p95/p99 and throughput.

### Commands

```bash
python scripts/15_benchmark_search.py
```

### Acceptance (Suggested)

- Text search p95 <= 3s (warm, realistic workload)
- Error rate < 1%

## Day 12 - Failure-Mode Hardening

### Tasks

- Add graceful degradation in search path:
  - reranker unavailable
  - single collection unavailable
  - timeout fallback
- Add explicit response metadata for degraded mode.

### Commands

```bash
pytest tests/ -k "search or vector" -v
```

### Acceptance

- Search returns partial but valid results in degraded conditions.

## Day 13 - Frontend/Backend Parity

### Tasks

- Audit and align:
  - `frontend/src/app/search/page.tsx`
  - `frontend/src/app/results/page.tsx`
  - `frontend/src/components/search/search-filters.tsx`
  - `frontend/src/components/search/similarity-mode-select.tsx`
  - `frontend/src/components/results/result-card.tsx`
  - `frontend/src/components/results/dimension-scores.tsx`
- Verify score scales and filter names match backend exactly.

### Commands

```bash
# from frontend/
npm test
```

### Acceptance

- UI output and backend payload semantics are consistent for all modes.

## Day 14 - UX + Legal Safety Pass

### Tasks

- Ensure all result pages include legal decision-support disclaimer.
- Improve no-result and low-confidence messaging.
- Validate export outputs (JSON/PDF fields and values).

### Acceptance

- No route can render search results without disclaimer text.

## Day 15 - Full Validation Sweep

### Commands

```bash
pytest tests/ -v
mypy src
python scripts/16_verify_index_integrity.py
python scripts/17_eval_retrieval_quality.py
python scripts/15_benchmark_search.py
```

### Acceptance

- All tests pass.
- Type check has no critical blockers.
- Integrity, quality, and performance reports pass release thresholds.

## Phase 2 Ship Gate (Final Checklist)

- [ ] Full tests pass.
- [ ] Retrieval eval metrics pass agreed thresholds for active eval dataset type.
- [ ] Benchmark SLO report passes.
- [ ] Index integrity checker passes.
- [ ] API contracts validated.
- [ ] Explanations evidence-grounded.
- [ ] Frontend parity verified.
- [ ] Runbook/docs updated under `docs/notes/`.

## Suggested Companion Docs

- `docs/notes/PHASE2_SCORING_SPEC.md`
- `docs/notes/PHASE2_API_CONTRACTS.md`
- `docs/notes/PHASE2_SLOS.md`
- `docs/notes/PHASE2_RUNBOOK.md`
- `docs/notes/PHASE2_HUMAN_EVAL_PLAN.md`
- `docs/notes/PHASE2_ANNOTATOR_HANDOFF_TEMPLATE.md`
