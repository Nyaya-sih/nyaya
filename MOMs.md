# MOMs - Technical Walkthrough (NyayaAI)

Last updated: 2026-04-06
Format: presentation-style engineering notes

## 1) Project Goal

NyayaAI is a legal decision-support platform for Indian case-law workflows.

Current delivered foundation:

- A full data engineering pipeline to clean and structure ~10K Indian High Court judgments
- A complete Similar Case Retrieval system (semantic + lexical + reranking)
- End-to-end API and frontend for search/upload/results/case-to-case similarity

## 2) What Was Built First: Data Foundation Pipeline

### Why this mattered

Everything downstream (retrieval, RAG, deliberation) depends on clean and structured data.

### Pipeline architecture

Implemented flow:

`download -> extract text -> extract metadata -> validate -> load -> validate at scale`

Core modules:

- Downloader: `src/data_pipeline/downloaders/hc_downloader.py`
- PDF extraction: `src/data_pipeline/extractors/pdf_extractor.py`
- LLM metadata extraction: `src/data_pipeline/extractors/metadata_extractor.py`
- Validation: `src/data_pipeline/validators/data_validator.py`
- Database loader: `src/data_pipeline/loaders/db_loader.py`

### Manual and scripted operational work done

- Multiple extraction and cleanup runs were done iteratively with logs under `docs/logs/`
- Court name normalization, duplicate handling, and quality reprocessing were performed in script-driven passes
- The dataset was expanded and stabilized to a 10K-class corpus with quality gates

Key resulting artifact:

- `data/processed/production_readiness_report.json`

### Data quality posture (latest report snapshot)

- total cases: 10,005
- non-invalid cases: 9,616
- average confidence: 0.7657
- invalid rate: 3.89%
- diverse court and year coverage is present

## 3) Database and Storage Layer

Primary persistence stack:

- PostgreSQL (structured case records)
- Qdrant (vector retrieval)
- Redis (available in infra stack)

Infra entrypoint:

- `docker-compose.yml`

DB model and schema files:

- ORM models: `src/database/models.py`
- Pydantic schemas: `src/database/schemas.py`

## 4) Phase 2 System: Similar Case Retrieval

### Core retrieval modules

- Embedding generation: `src/features/similar_cases/embedding_generator.py`
- Vector search/filtering: `src/features/similar_cases/vector_store.py`
- Search orchestration and ranking logic: `src/features/similar_cases/search_engine.py`
- Cross-encoder reranker: `src/features/similar_cases/reranker.py`
- Explainability layer: `src/features/similar_cases/similarity_analyzer.py`

### Embedding technicalities

Implemented multi-representation strategy:

- factual embedding
- legal embedding
- outcome embedding
- combined weighted embedding
- fulltext-lite embedding path for long-judgment retrieval mode

Operational scripts:

- `scripts/13_generate_embeddings.py`
- `scripts/14_generate_fulltext_embeddings.py`

Index sync and manifest reliability:

- `scripts/18_sync_vector_index.py`
- `scripts/19_rebuild_embedding_manifest.py`

### How retrieval is fetched at runtime

Runtime path in API requests:

1. query text (or uploaded document text) is prepared and summarized
2. query embedding is generated
3. vector candidates are fetched from selected collection(s)
4. optional hybrid lexical fusion is applied
5. optional reranker reorders candidates
6. explanation dimensions are generated per result
7. response returns ranked cases + disclaimer + warnings + retrieval mode

API routes exposed:

- `POST /api/v1/cases/similar`
- `POST /api/v1/cases/similar/upload`
- `GET /api/v1/cases/{case_id}`
- `GET /api/v1/cases/{case_id}/similar`
- `POST /api/v1/cases/explain`
- `GET /api/v1/cases/search/filters`

Route definitions:

- `src/features/similar_cases/router.py`

## 5) Frontend Delivery for Similar Search

Frontend stack:

- Next.js + TypeScript
- React Query for data fetching
- Zustand for client state

Implemented user flows:

- text search
- upload-based search
- filter selection
- result cards and scoring breakdown
- case detail and "find similar"
- legal disclaimer display

Primary files:

- `frontend/src/app/search/page.tsx`
- `frontend/src/app/results/page.tsx`
- `frontend/src/lib/api/search.ts`
- `frontend/src/components/results/legal-disclaimer.tsx`

## 6) Quality, Reliability, and Benchmarking

Test coverage:

- `tests/` includes API contract tests, search tests, vector tests, eval tooling tests, and regression tests
- Latest full run: 96 passing tests

Operational gate scripts:

- benchmark: `scripts/15_benchmark_search.py`
- index integrity: `scripts/16_verify_index_integrity.py`
- retrieval quality: `scripts/17_eval_retrieval_quality.py`

Latest gate artifacts:

- `data/processed/benchmark_results.json`
- `data/processed/index_integrity_report.json`
- `data/processed/retrieval_eval_report.json`

## 7) Human Evaluation Track (Prepared, Deferred)

Prepared workflow:

- packet generation: `scripts/21_generate_human_eval_packets.py`
- annotation validation: `scripts/23_validate_human_annotations.py`
- reviewer batch split/merge: `scripts/24_export_annotation_batch.py`, `scripts/25_merge_annotator_batches.py`
- gold generation: `scripts/22_build_human_gold_from_packets.py`

Current decision:

- human annotation execution is intentionally deferred for now

## 8) Current Project Position

- Phase 1 complete
- Phase 2 engineering-complete, sign-off pending hardening/human-eval completion
- Phase 3 and Phase 4 are the next major build targets

Canonical project status file:

- `docs/notes/PROJECT_STATUS.md`

## 9) Practical Takeaway

This project already has a real data product backbone, a production-style retrieval engine, and a functioning frontend/API loop. The next leap is feature expansion (Phase 3 and 4) rather than rebuilding foundations.
