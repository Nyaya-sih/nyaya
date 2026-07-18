# Phase 3 Plan - Legal Research Assistant (RAG)

Last updated: 2026-04-07
Status: completed

## 1) Goal

Build Feature 2 from `nyaya-ai-project-prompt.md`: a legal research assistant that answers questions about Indian law and case documents using retrieval-augmented generation (RAG), with citations, confidence indicators, and session memory.

This is a decision-support assistant, not legal advice.

## 2) Scope for Phase 3

### In scope

- Conversational API for legal Q&A
- Active case context (uploaded or existing case id)
- Hybrid retrieval from:
  - cleaned case corpus (Postgres + Qdrant)
  - legal knowledge chunks (statutes/constitution corpus)
- Prompt orchestration with source attribution
- Citation-first response schema
- Confidence scoring based on retrieval and answer coverage
- Basic conversation memory per session
- Frontend chat UI integration
- Test suite, eval harness, and runbook updates

### Out of scope (defer)

- Fine-tuning/LoRA training pipeline
- Full multi-tenant auth/RBAC
- Heavy production observability stack
- Advanced legal drafting copilots

## 3) Success Criteria (release gate for Phase 3)

- API:
  - stable assistant endpoints under `/api/v1/assistant/*`
  - deterministic response schema with citations
- Retrieval:
  - top-k chunks include relevant statute/case passages for benchmark queries
- Safety and transparency:
  - mandatory disclaimer in every response
  - explicit uncertainty behavior (assistant says when unsure)
- Quality:
  - citation coverage >= 90% of substantive claims in curated test prompts
  - hallucination rate below agreed threshold on evaluation set
- Performance:
  - p95 response latency within agreed envelope for non-streaming mode
- Engineering:
  - tests pass
  - docs/runbook updated

## 4) High-Level Architecture

### 4.1 Request flow

1. User asks query (optionally with active case context)
2. Query parser extracts intent + legal entities (statutes/sections/case terms)
3. Retriever fetches relevant evidence from:
   - case vectors (Qdrant)
   - statute/constitution vectors (new legal KB index)
4. Context builder composes bounded evidence pack
5. LLM answer generator creates response constrained to evidence
6. Citation validator checks references map to retrieved sources
7. Confidence estimator scores answer confidence
8. Response formatter returns answer, citations, confidence, disclaimer

### 4.2 Components to add

- `src/features/legal_assistant/router.py`
- `src/features/legal_assistant/schemas.py`
- `src/features/legal_assistant/session_store.py`
- `src/features/legal_assistant/query_parser.py`
- `src/features/legal_assistant/retriever.py`
- `src/features/legal_assistant/context_builder.py`
- `src/features/legal_assistant/answer_generator.py`
- `src/features/legal_assistant/citation_validator.py`
- `src/features/legal_assistant/confidence.py`
- `src/features/legal_assistant/service.py`
- frontend chat page and components

### 4.3 Existing assets reused

- Qdrant and embedding infrastructure from Phase 2
- Document extraction utility: `src/utils/document_processor.py`
- settings and API app infrastructure in `src/config/settings.py` and `src/api/main.py`

## 5) Data and Indexing Plan

### 5.1 Legal knowledge corpus

Create a normalized corpus for:

- Constitution of India (articles and amendments)
- IPC/BNS
- CrPC/BNSS
- CPC
- Evidence Act/BSA
- key statutes (IT Act, POCSO, NDPS, Companies Act, etc.)

Expanded target corpus for production-grade Indian legal assistant:

- Constitutional framework
  - Constitution of India (current amended text)
  - Constitutional Amendment Acts as separate traceable sources
- Core central legislation
  - Bharatiya Nyaya Sanhita (BNS), 2023
  - Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023
  - Bharatiya Sakshya Adhiniyam (BSA), 2023
  - Indian Penal Code, 1860 (tagged superseded)
  - Code of Criminal Procedure, 1973 (tagged superseded)
  - Indian Evidence Act, 1872 (tagged superseded)
  - Code of Civil Procedure, 1908
  - Indian Contract Act, 1872
  - Transfer of Property Act, 1882
  - Specific Relief Act, 1963
  - Limitation Act, 1963
  - Companies Act, 2013
  - Information Technology Act, 2000 (+ 2008 amendment context)
  - Consumer Protection Act, 2019
  - RTI Act, 2005
  - Motor Vehicles Act, 1988
  - POCSO Act, 2012
  - Prevention of Corruption Act, 1988
  - Arbitration and Conciliation Act, 1996
  - Insolvency and Bankruptcy Code, 2016
- Procedural and court rules
  - Supreme Court Rules, 2013
  - selected High Court Rules (scope by targeted jurisdictions)
  - Civil Rules of Practice
  - Criminal Rules of Practice
  - order/rule procedural mappings for CPC/BNSS
- Subordinate legislation
  - schedules under major Acts
  - key central rules (example: IT Rules 2021, companies rules)
  - state-specific laws only when jurisdiction scope is enabled
- Secondary sources (curated)
  - Law Commission of India reports (curated subset first)
  - legal maxims and terminology glossary
  - NJDG procedural guidance documents
  - Bar Council of India rules (for conduct/profession queries)

### 5.2 Chunking strategy

- statute-first chunking by structural units (article/section/subsection)
- sliding window fallback for long sections
- preserve metadata per chunk:
  - `source_type` (`constitution`, `statute`, `case`)
  - `act_name`
  - `article_or_section`
  - `title`
  - `year`
  - `jurisdiction`
  - `citation_id`

Non-negotiable chunking rule:

- chunk by legal unit (`section`/`article`/`rule`), not by PDF page
- each chunk should include full sub-clauses and explanation notes when present
- each chunk header should carry parent act/rule identity and amendment status

Required metadata additions:

- `chapter_or_part`
- `is_superseded` (bool)
- `superseded_by` (nullable string)
- `effective_from` and `effective_to` (nullable date strings)
- `source_url`
- `source_version_hash`

### 5.3 Vector storage

- new Qdrant collection: `nyaya_legal_kb`
- use same embedding model initially for consistency
- payload index fields for fast filter support

Recommended payload indexes:

- `source_type`
- `act_name`
- `section_or_article`
- `chapter_or_part`
- `is_superseded`
- `jurisdiction`
- `year`

### 5.4 Index scripts

Add scripts:

- `scripts/30_prepare_legal_kb.py` (normalize + chunk)
- `scripts/31_index_legal_kb.py` (embed + upsert)
- `scripts/32_verify_legal_kb_integrity.py` (counts/metadata checks)

Source ingestion guidance:

- primary source preference: India Code (`indiacode.nic.in`) due to cleaner structure
- preserve upstream reference and retrieval timestamp in metadata
- create deterministic ids for every chunk:
  - `<source_type>:<act_slug>:<section_or_article>:<version_hash>`

## 6) API Design (Phase 3)

Base prefix: `/api/v1/assistant`

### 6.1 Endpoints

- `POST /session`
  - create session
  - response: `session_id`, ttl, created_at
- `POST /session/{session_id}/context/upload`
  - upload case document (pdf/docx/text)
  - extracts text and sets active case context
- `POST /session/{session_id}/context/case/{case_id}`
  - sets active context from existing case
- `POST /query`
  - body: `session_id`, `question`, optional retrieval knobs
  - returns: `answer`, `citations[]`, `confidence`, `disclaimer`, `warnings[]`
- `GET /session/{session_id}/history`
  - returns prior turns (bounded)
- `DELETE /session/{session_id}`
  - clear session memory/context

### 6.2 Response schema

Mandatory fields:

- `answer_text`
- `citations` array where each item has:
  - `citation_id`
  - `source_type`
  - `title`
  - `act_or_case`
  - `section_or_article` (nullable)
  - `excerpt`
  - `score`
- `confidence` object:
  - `overall` in [0,1]
  - `retrieval_support`
  - `citation_coverage`
  - `risk_flags[]`
- `disclaimer`

## 7) Retrieval Strategy

### 7.1 Multi-source retrieval

- Query embedding -> retrieve from case collection and legal KB collection
- Merge candidates with weighted blend:
  - legal KB relevance
  - case relevance
  - lexical overlap bonus
- Apply filters if active case context exists (case type/court/year)

### 7.2 Ranking

- Stage 1: vector candidate retrieval
- Stage 2: lightweight rerank using query-chunk textual relevance
- Stage 3 (optional): cross-encoder rerank for final top-k context pack

### 7.3 Context budget

- enforce token budget cap
- diverse evidence selection (statute + case mix)
- deduplicate near-identical chunks

## 8) Prompting and Answer Generation

### 8.1 System behavior

- Only answer from provided evidence
- If insufficient support, explicitly say unsure
- Do not fabricate sections/case citations
- Use Indian legal terminology

### 8.2 Prompt sections

- role and policy constraints
- user question
- active case summary (if present)
- retrieved evidence blocks with citation ids
- output schema instruction

### 8.3 Post-generation validation

- check each cited id exists in retrieval set
- downgrade confidence on unsupported assertions
- inject warning if support is thin

## 9) Confidence and Safety

### 9.1 Confidence calculation

Weighted composite:

- retrieval support score
- citation density/coverage
- contradiction/ambiguity checks
- model self-reported uncertainty signal (bounded)

### 9.2 Safety controls

- hard disclaimer attached to every answer
- reject non-legal or abusive prompts with safe response
- no deterministic legal advice language

## 10) Frontend Plan

Add assistant UI in frontend:

- page: `/assistant`
- panels:
  - active case context
  - chat thread
  - citations drawer
  - confidence badge and warnings
- actions:
  - upload case
  - select existing case
  - ask follow-up questions

Key files to add:

- `frontend/src/app/assistant/page.tsx`
- `frontend/src/components/assistant/*`
- `frontend/src/lib/api/assistant.ts`
- `frontend/src/lib/api/types.ts` (assistant types)

## 11) Iterative Implementation Plan

### Iteration 0 - Scaffolding and contracts

Deliverables:

- module scaffolds under `src/features/legal_assistant/`
- pydantic request/response schemas
- API router with placeholder responses

Acceptance:

- contract tests compile and pass for schema shape

### Iteration 1 - Session and context management

Deliverables:

- in-memory session store (upgrade path to Redis)
- context upload and context-by-case-id endpoints
- bounded turn history persistence

Acceptance:

- session lifecycle tests pass
- upload parsing works for pdf/docx/text

### Iteration 2 - Legal KB ingestion and index

Deliverables:

- corpus prep and chunking scripts
- `nyaya_legal_kb` indexing script
- integrity checker and report

Detailed deliverables:

- source manifest with jurisdiction and priority tiers
- parser adapters for html/pdf text extraction into canonical legal units
- supersession map for IPC/CrPC/Evidence Act -> BNS/BNSS/BSA
- metadata validator rejecting chunks missing act/section identity

Acceptance:

- index contains expected chunk counts and metadata
- superseded-law queries route to both old and replacement laws with explicit tagging

### Iteration 3 - Retriever service

Deliverables:

- multi-source retriever (case + legal kb)
- merge/rank logic
- configurable top-k and thresholds

Acceptance:

- retrieval unit tests for filter semantics and ordering

### Iteration 4 - Answer generation and citation validator

Deliverables:

- prompt builder + LLM call
- citation validator and normalization
- confidence estimator

Acceptance:

- responses always include valid citation ids
- unsupported claims flagged

### Iteration 5 - End-to-end assistant endpoint

Deliverables:

- `POST /api/v1/assistant/query` fully functional
- history-aware follow-up support

Acceptance:

- integration tests pass for first-turn and follow-up paths

### Iteration 6 - Frontend integration

Deliverables:

- assistant page, context controls, chat rendering
- citation panel and confidence display

Acceptance:

- frontend build/lint pass
- manual e2e smoke test with backend

### Iteration 7 - Eval harness and tuning

Deliverables:

- `scripts/33_eval_assistant_quality.py`
- curated query set and expected citation checks

Acceptance:

- defined quality metrics generated and tracked

### Iteration 8 - Hardening and docs

Deliverables:

- runbook updates
- error handling and fallback polishing
- API docs finalization

Acceptance:

- full tests green
- phase status doc updated

## 12) Testing Strategy

### Unit tests

- query parser
- retriever merge/rank logic
- citation validator
- confidence scoring

### Integration tests

- session lifecycle
- upload + query path
- context from existing case path
- citation integrity in final answer

### Regression tests

- fixed legal questions with expected citation families
- no-schema-drift contract tests

## 13) Risks and Mitigations

- Risk: knowledge base data quality inconsistency
  - Mitigation: strict chunk metadata schema and validation script
- Risk: hallucinated citations
  - Mitigation: citation validator + confidence penalty + explicit uncertainty
- Risk: latency spike due to multi-source retrieval
  - Mitigation: capped candidates, cache frequent prompts, optional no-rerank mode
- Risk: session memory bloat
  - Mitigation: bounded history window and ttl expiration

## 14) Tonight Execution Strategy (fast track)

If the objective is rapid progress tonight:

1. finish Iteration 0 + 1 first (contracts + sessions + context)
2. implement Iteration 3 and 4 in parallelizable steps (retriever + generator)
3. deliver backend-first working assistant endpoint
4. then integrate minimal frontend chat page
5. leave advanced eval tuning for next pass

This gives a working Phase 3 MVP while preserving quality and extensibility.
