# MOMs - Technical Walkthrough (NyayaAI)

Last updated: 2026-04-07
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

## 8) Phase 3 Delivery: Legal Research Assistant (Completed)

### Backend and API

- Assistant endpoints delivered under `src/features/legal_assistant/router.py`:
  - `POST /api/v1/assistant/session`
  - `POST /api/v1/assistant/session/{session_id}/context/upload`
  - `POST /api/v1/assistant/session/{session_id}/context/case/{case_id}`
  - `POST /api/v1/assistant/query`
  - `GET /api/v1/assistant/session/{session_id}/history`
  - `DELETE /api/v1/assistant/session/{session_id}`
- Session lifecycle, context management, citation validation, confidence scoring, and response formatting are implemented.
- Retrieval now blends active case/session context with legal KB vector retrieval.
- Assistant responses are prompt-tuned for professional legal drafting style with numbered citations (e.g., `CIT-1`).

### Legal KB corpus and embedding work

- A large Indian legal corpus was prepared/chunked and embedded, including:
  - Constitution of India
  - BNS / BNSS / BSA
  - IPC / CrPC / Evidence Act (superseded-tagged where applicable)
  - CPC and major central statutes (Companies Act, IT Act, Consumer Act, MVA, POCSO, PCA, Arbitration, IBC, etc.)
  - procedural/court rules + curated Law Commission reports + glossary/mapping notes
- Embedding artifacts:
  - per-act vectors in `legal_kb/embeddings/*.npy`
  - FAISS index in `legal_kb/faiss/legal_kb.index`
  - metadata and text lookup maps in `legal_kb/faiss/chunk_id_map.json` and `legal_kb/faiss/chunk_text_lookup.json`

### Frontend assistant UX

- Assistant page added at `frontend/src/app/assistant/page.tsx`
- Frontend API/hooks added for assistant interaction:
  - `frontend/src/lib/api/assistant.ts`
  - `frontend/src/lib/hooks/use-assistant.ts`

### Evaluation and execution scripts

- Assistant quality harness added:
  - `scripts/33_eval_assistant_quality.py`
- Legal KB build/fix/embed pipeline scripts added:
  - `scripts/34_generate_legal_kb_chunks.py`
  - `scripts/35_fix_legal_kb_quality.py`
  - `scripts/36_targeted_refetch_rechunk.py`
  - `scripts/37_finalize_pre_embedding.py`
  - `scripts/38_embed_legal_kb.py`

## 9) Phase 4 Delivery: Simulated Courtroom (Engineering-Complete)

### Backend and API

- Courtroom endpoints delivered under `src/features/courtroom/router.py`:
  - `POST /api/v1/courtroom/analyze`
  - `GET /api/v1/courtroom/analysis/{analysis_id}`
  - `GET /api/v1/courtroom/analysis/{analysis_id}/status`
  - `POST /api/v1/courtroom/analysis/{analysis_id}/cancel`
- Role-based deliberation pipeline implemented with reusable modules:
  - role prompts/model routing: `roles.py`, `model_registry.py`
  - parallel role analysis + retrieval integration: `analysis_engine.py`, `orchestrator.py`, `retrieval_adapter.py`
  - anonymous peer scoring + rebuttal + judge synthesis: `evaluation_engine.py`, `rebuttal_engine.py`, `synthesis_engine.py`
- Transparency and resilience features implemented:
  - anonymized scoring matrix and criteria breakdown
  - degraded-mode execution for partial provider/role failures
  - deterministic repeat-run cache and cost/token estimation

### LLM provider extensibility updates

- Provider routing made more extensible with OpenAI, Gemini/Google alias handling, and Groq support.
- Settings and env support expanded with courtroom-specific knobs and provider key discovery.
- Goal achieved: swap provider/model combinations without rewriting courtroom orchestration logic.

### Frontend courtroom UX

- Courtroom interface added at `frontend/src/app/courtroom/page.tsx` with mode/source controls and report rendering.
- Frontend API/hooks and types implemented:
  - `frontend/src/lib/api/courtroom.ts`
  - `frontend/src/lib/hooks/use-courtroom.ts`
  - `frontend/src/lib/api/types.ts`
- Navbar route enabled for both Assistant and Courtroom pages.

### Testing and evaluation

- Courtroom contract and logic tests added:
  - `tests/test_api_contract_courtroom.py`
  - `tests/test_courtroom_scoring.py`
- Backend suite currently green at `114 passed`.
- Frontend lint currently green.
- Courtroom quality harness added:
  - `scripts/39_eval_courtroom_quality.py`
  - latest report: `data/processed/courtroom_eval_report.json`

## 10) Current Project Position

- Phase 1 complete
- Phase 2 engineering-complete, sign-off pending hardening/human-eval completion
- Phase 3 complete
- Phase 4 engineering-complete; production sign-off pending live-provider reliability pass

Canonical project status file:

- `docs/notes/PROJECT_STATUS.md`

## 11) Practical Takeaway

This project now has a real data product backbone, production-style retrieval, a legal assistant, and a multi-agent courtroom deliberation engine. The next leap is Phase 5 forecasting/outcome tendency features and release hardening, not foundational rebuild.
