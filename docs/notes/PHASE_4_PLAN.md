# Phase 4 Plan - Simulated Courtroom (Multi-Model Deliberation Engine)

Last updated: 2026-04-07  
Status: executed (engineering-complete; see `docs/notes/PHASE4_COMPLITION.md`)

## 1) Goal

Build Feature 1 from `nyaya-ai-project-prompt.md`: a simulated courtroom engine where multiple role-based legal agents analyze the same case, score each other on a structured rubric, optionally rebut critiques, and produce a judge-style synthesized recommendation with transparent scoring and caveats.

This is a decision-support workflow, not legal advice.

## 2) Scope for Phase 4

### In scope

- Case-centric multi-role analysis pipeline:
  - Prosecution Counsel
  - Defense Counsel
  - Constitutional Expert
  - Legal Analyst
  - Presiding Judge (synthesis role)
- Role-specific prompt packs and output contracts
- Anonymous cross-evaluation scoring matrix (non-judge roles score other non-judge roles)
- Optional rebuttal round and second-pass scoring
- Final synthesis by Presiding Judge
- Transparency artifacts:
  - score heatmap
  - criteria-level breakdown
  - consensus/disagreement indicators
  - confidence summary + caveats
- Cost and latency reporting per analysis run
- Quick mode and Full mode:
  - Quick: fewer roles / no rebuttal / lower latency
  - Full: all roles + rebuttal + richer report
- Graceful degradation when one or more model calls fail
- Frontend courtroom workflow and report rendering
- Tests, evaluation harness, runbook/docs

### Out of scope (defer)

- Real-time courtroom voice/audio simulation
- Full evidentiary graph reasoning engine
- Production-scale RBAC and tenant isolation
- Full streaming architecture (WebSocket can be added as a phase-4.5 enhancement)
- Heavy BI/analytics platform for longitudinal courtroom sessions

## 3) Success Criteria (Phase 4 Release Gate)

- API:
  - stable endpoints under `/api/v1/courtroom/*`
  - deterministic response schema for all completed analyses
- Deliberation logic:
  - all configured roles complete initial analysis or are transparently marked degraded
  - cross-evaluation matrix generated with criteria-level scores and textual justifications
  - rebuttal pass works when enabled and is excluded cleanly when disabled
- Synthesis quality:
  - final synthesis explicitly lists consensus points, disagreement points, and unresolved issues
  - final recommendation includes confidence and caveats
- Transparency and safety:
  - mandatory legal disclaimer in every final response
  - explicit mention when evidence/support is weak
  - source-linked citations for key legal claims
- Performance:
  - Quick mode: p95 end-to-end <= 180s (target)
  - Full mode: p95 end-to-end <= 720s (target)
- Engineering:
  - unit/integration tests green
  - docs and runbook updated

## 4) High-Level Architecture

### 4.1 End-to-end flow

1. User submits case input + mode (`quick` or `full`) + optional knobs
2. System creates `analysis_id` and initializes run state
3. Retrieval layer gathers legal evidence pack (statutes/constitution + optional similar cases)
4. Role analysis stage runs role prompts in parallel (except judge)
5. Outputs are anonymized and routed to cross-evaluation stage
6. Each non-judge role scores other non-judge outputs using rubric
7. If rebuttal enabled:
   - each role receives critiques
   - each role submits revised analysis
   - second scoring pass executes
8. Presiding Judge receives all material and generates final synthesis
9. Report assembler returns:
   - executive summary
   - role analyses
   - scoring dashboard payload
   - caveats/disclaimer
   - cost + timing diagnostics

### 4.2 Core components to add

- `src/features/courtroom/router.py`
- `src/features/courtroom/schemas.py`
- `src/features/courtroom/service.py`
- `src/features/courtroom/orchestrator.py`
- `src/features/courtroom/roles.py`
- `src/features/courtroom/retrieval_adapter.py`
- `src/features/courtroom/analysis_engine.py`
- `src/features/courtroom/evaluation_engine.py`
- `src/features/courtroom/rebuttal_engine.py`
- `src/features/courtroom/synthesis_engine.py`
- `src/features/courtroom/scoring.py`
- `src/features/courtroom/anonymizer.py`
- `src/features/courtroom/cost_tracker.py`
- `src/features/courtroom/run_store.py`

Frontend:

- `frontend/src/app/courtroom/page.tsx`
- `frontend/src/components/courtroom/*`
- `frontend/src/lib/api/courtroom.ts`
- `frontend/src/lib/hooks/use-courtroom.ts`
- `frontend/src/lib/api/types.ts` (courtroom types)

### 4.3 Existing assets to reuse

- `src/utils/llm_client.py` for multi-provider LLM access + retry/cost tracking
- `src/features/legal_assistant/retriever.py` legal KB retrieval patterns
- `legal_kb/faiss/*` and embedded legal corpus from Phase 3
- `src/utils/document_processor.py` upload extraction support
- API wiring and dependency patterns in `src/api/main.py` and `src/api/dependencies.py`

## 5) Data Model and Persistence Plan

Use JSON-first persistence with an upgrade path to relational tables.

### 5.1 Run-level entity

- `analysis_id`
- `status`: `queued | running | completed | degraded | failed`
- `mode`: `quick | full`
- `created_at`, `started_at`, `completed_at`
- `input_source`: `upload | case_id | text`
- `warnings[]`, `errors[]`

### 5.2 Role analysis entity

- `role_name`
- `analysis_text`
- `citations[]`
- `confidence`
- `latency_ms`
- `model_metadata` (provider, model)

### 5.3 Evaluation entity

- `evaluator_role`
- `target_analysis_ref` (anonymous id)
- `criteria_scores`:
  - legal_accuracy
  - constitutional_alignment
  - logical_coherence
  - precedent_usage
  - fairness_balance
  - practical_applicability
- `weighted_score`
- `justification`

### 5.4 Rebuttal entity (optional)

- `role_name`
- `received_critiques[]`
- `revised_analysis_text`
- `revision_notes`

### 5.5 Final synthesis entity

- `executive_summary`
- `consensus_points[]`
- `disagreement_points[]`
- `recommended_outcome`
- `confidence` (0-1)
- `unresolved_questions[]`
- `legal_principles_applied[]`

### 5.6 Transparency entity

- score matrix (role x role)
- criteria-level aggregate stats
- disagreement index
- consensus meter
- estimated run cost + token usage

## 6) API Design (Phase 4)

Base prefix: `/api/v1/courtroom`

### 6.1 Endpoints

- `POST /analyze`
  - starts analysis run
  - returns `analysis_id`, status, eta estimate
- `GET /analysis/{analysis_id}`
  - returns full completed/degraded report
- `GET /analysis/{analysis_id}/status`
  - lightweight status/progress payload
- `POST /analysis/{analysis_id}/cancel`
  - best-effort cancellation if still running

Optional phase-4.5:

- `GET /analysis/{analysis_id}/stream` (SSE/WebSocket)

### 6.2 Request shape (high-level)

- `mode`: `quick|full`
- `source`: upload/case/text
- `include_rebuttal`: bool (default false in quick, true in full)
- `top_k_legal`, `top_k_cases`
- `role_model_overrides` (optional)
- `max_cost_usd` guardrail (optional)

### 6.3 Response shape (high-level)

- `analysis_id`, `status`, `mode`
- `executive_summary`
- `role_analyses[]`
- `evaluation_breakdown`
- `rebuttal_changes` (if enabled)
- `synthesis`
- `transparency_dashboard`
- `disclaimer`
- `warnings[]`

## 7) Role Prompting and Deliberation Rules

### 7.1 Role prompt packs

Each role gets:

- role mandate
- what to prioritize
- what to avoid
- strict output schema
- citation requirements

Role mandates:

- Prosecution Counsel: strongest prosecution/petitioner framing
- Defense Counsel: strongest defense/respondent framing
- Constitutional Expert: constitutional validity + rights implications
- Legal Analyst: neutral procedural/evidentiary/legal-merit analysis
- Presiding Judge: synthesis only (no scoring participation)

### 7.2 Cross-evaluation rubric (fixed weights)

- Legal Accuracy: 25%
- Constitutional Alignment: 20%
- Logical Coherence: 20%
- Precedent Usage: 15%
- Fairness & Balance: 10%
- Practical Applicability: 10%

Rules:

- score range 1-100 per criterion
- mandatory justification
- no self-scoring
- judge excluded from scoring phase

### 7.3 Rebuttal mode

When enabled:

- each role receives anonymized critiques of own output
- revised output must include:
  - what changed
  - why changed
  - what remains contested
- second scoring pass computes revised weighted scores

## 8) Retrieval and Evidence Strategy for Courtroom

- Evidence source mix:
  - Legal KB FAISS (Phase 3 assets)
  - optional similar case retrieval (Phase 2 engine)
- Role-aware retrieval prompts:
  - prosecution/defense get adversarially useful material
  - constitutional expert gets rights/articles emphasis
  - legal analyst gets procedural/evidentiary balance
- Deduplicate near-identical evidence before prompt packing
- Apply bounded context per role to avoid prompt bloat
- Enforce source attribution fields for all extracted legal claims

## 9) Cost, Latency, and Reliability Controls

- Parallelize non-dependent model calls
- Concurrency caps per provider
- Retry with bounded exponential backoff
- Fallback/degrade policy:
  - if one role fails -> continue with remaining roles and warning
  - if judge fails -> return deliberation report with explicit incomplete synthesis status
- Cache completed analysis by deterministic case hash + mode + key knobs
- Expose token/cost estimates in response for transparency

## 10) Frontend Experience Plan

### 10.1 Courtroom page UX

- Input panel:
  - upload case / choose existing case
  - mode toggle (Quick/Full)
  - rebuttal toggle
- Progress panel:
  - stage-by-stage timeline (analysis -> scoring -> rebuttal -> synthesis)
- Results tabs:
  - Executive Summary
  - Role Analyses
  - Scoring Dashboard (heatmap + criterion bars)
  - Rebuttal Diff (if enabled)
  - Caveats and Cost

### 10.2 Visual trust cues

- explicit disclaimer block
- confidence and consensus badges
- warnings when degraded/incomplete

## 11) Iterative Implementation Plan

### Iteration 0 - Contracts and Scaffolding

Deliverables:

- courtroom module skeleton
- request/response schemas
- placeholder endpoints and run status object

Acceptance:

- contract tests pass for schema and endpoint shape

### Iteration 1 - Role Analysis Engine (No scoring yet)

Deliverables:

- role prompt packs
- parallel role analysis calls (excluding judge)
- structured role outputs with citations

Acceptance:

- quick mode returns 3-4 role analyses reliably

### Iteration 2 - Retrieval Integration

Deliverables:

- role-aware evidence retrieval adapter
- bounded prompt context assembly per role

Acceptance:

- role outputs cite relevant legal sources for benchmark prompts

### Iteration 3 - Anonymous Cross-Evaluation

Deliverables:

- anonymizer + evaluator routing
- rubric scoring + weighted aggregation
- matrix and criterion summaries

Acceptance:

- scoring matrix is complete and self-score-free

### Iteration 4 - Rebuttal Round

Deliverables:

- critique packaging for each role
- revised analysis generation
- second-pass scoring and delta summaries

Acceptance:

- full mode includes rebuttal outputs and score deltas

### Iteration 5 - Judge Synthesis

Deliverables:

- presiding judge synthesis prompt and output schema
- consensus/disagreement extraction
- final recommendation with caveats

Acceptance:

- synthesis always includes unresolved issues and confidence

### Iteration 6 - Persistence, Caching, and Degrade Paths

Deliverables:

- run store with status lifecycle
- deterministic run hash caching
- robust degraded responses for partial failures

Acceptance:

- failed role calls no longer crash full run; status is transparent

### Iteration 7 - Frontend Courtroom UI

Deliverables:

- `/courtroom` page end-to-end integration
- stage progress UI + reports + dashboard widgets

Acceptance:

- manual E2E smoke: submit case -> view final report and matrix

### Iteration 8 - Evaluation Harness

Deliverables:

- `scripts/39_eval_courtroom_quality.py`
- curated scenario set (criminal/civil/constitutional)
- metrics generation (coherence, citation support, consensus stability)

Acceptance:

- baseline metrics generated and stored under `data/processed/`

### Iteration 9 - Hardening and Docs

Deliverables:

- runbook and ops notes
- API docs finalization
- performance and cost tuning pass

Acceptance:

- full tests green, docs updated, release checklist signed

## 12) Testing Strategy

### Unit tests

- scoring weight calculations
- anonymization correctness
- rebuttal merge/diff logic
- consensus/disagreement metric computation

### Integration tests

- quick mode full lifecycle
- full mode with rebuttal lifecycle
- degraded mode when one role fails
- citation validation in synthesized output

### Regression tests

- fixed courtroom prompts with expected rubric stability bands
- no-schema-drift checks for courtroom API payloads

## 13) Risks and Mitigations

- Risk: role outputs converge to similar generic text
  - Mitigation: strong role-specific constraints and adversarial objectives
- Risk: high latency/cost in full mode
  - Mitigation: aggressive parallelism, caching, optional provider mix, max-cost guardrails
- Risk: hallucinated citations in synthesis
  - Mitigation: citation validator pass + unsupported-claim warning injection
- Risk: brittle scoring due to model variance
  - Mitigation: deterministic rubric prompts, optional low-temperature scoring calls, variance tracking in eval harness

## 14) Immediate Execution Order (Fast Start)

1. Iteration 0 + 1 (contracts + role analysis core)
2. Iteration 2 + 3 (retrieval + cross-evaluation)
3. Iteration 5 (judge synthesis) before rebuttal to ship first usable MVP
4. Iteration 4 (rebuttal) as quality upgrade
5. Iteration 7/8/9 for UI, eval, and hardening

This order gives a usable courtroom MVP early while preserving full-phase architecture goals.
