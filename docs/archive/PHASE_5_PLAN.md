# Phase 5 Plan - Outcome Tendency Analyzer (Statistical Insights)

Last updated: 2026-04-08
Status: planned (execution next)

## 1) Goal

Build Feature 4 from `nyaya-ai-project-prompt.md`: a case outcome tendency analyzer that provides historical pattern insights from similar cases.

This is a decision-support workflow, not legal advice and not verdict prediction.

## 2) Critical Framing and Safety Guardrails

- Never frame outputs as predicting the verdict.
- Always frame as historical pattern analysis over comparable cases.
- Always show sample size and confidence/uncertainty context.
- Always include legal disclaimer and limitation caveats.
- Never imply judicial certainty from model probabilities.

## 3) Scope for Phase 5

### In scope

- Endpoint for outcome tendency analysis under `/api/v1/cases/tendency`.
- Deterministic baseline tendency engine (non-ML first):
  - cohort matching by case type, court, statute, and date windows
  - outcome distribution and sentence summary where available
  - trend slices by year/court
- Feature-store style extraction pipeline for trainable models.
- Model training benchmark track (logreg, random forest, xgboost/lightgbm if available).
- Probability calibration and confidence band reporting.
- Explainability payload (feature importances / SHAP or fallback importances).
- Frontend tendency dashboard with explicit disclaimers.
- Bias and coverage checks (slice-level drift and disparity flags).
- Evaluation harness and report artifact under `data/processed/`.

### Out of scope (defer)

- Any UI language that can be interpreted as deterministic verdict prediction.
- Judge-specific personalization or attorney-specific recommendations.
- Full causal inference claims.
- Automated legal strategy recommendations.

## 4) Success Criteria (Phase 5 Release Gate)

- API returns stable schema with explicit disclaimer and caveats in every response.
- Baseline deterministic tendency works without requiring model training.
- If ML mode enabled, calibrated probabilities and confidence metadata are present.
- Coverage transparency is explicit:
  - sample size
  - cohort filters used
  - insufficient-data warning path
- Bias/quality checks produce a report artifact and warning flags.
- Tests pass for API contracts, deterministic math, and safety framing.

## 5) High-Level Architecture

1. Input case (text/upload/case_id) normalized into case profile.
2. Cohort selector pulls comparable cases from existing DB/retrieval assets.
3. Baseline stats engine computes:
   - outcome distribution
   - sentence distribution (if criminal)
   - trend shifts over time
4. Optional ML scorer computes calibrated tendency probabilities.
5. Explainability engine computes key influencing factors.
6. Response assembler returns dashboard payload + caveats + disclaimer.

## 6) Backend Components to Add

- `src/features/outcome_tendency/router.py`
- `src/features/outcome_tendency/schemas.py`
- `src/features/outcome_tendency/service.py`
- `src/features/outcome_tendency/cohort_selector.py`
- `src/features/outcome_tendency/stats_engine.py`
- `src/features/outcome_tendency/feature_builder.py`
- `src/features/outcome_tendency/model_runner.py`
- `src/features/outcome_tendency/calibration.py`
- `src/features/outcome_tendency/explainability.py`
- `src/features/outcome_tendency/bias_audit.py`
- `src/features/outcome_tendency/reporting.py`

Integration wiring:

- `src/api/main.py` router mount
- `src/api/dependencies.py` service provider

## 7) API Design (Phase 5)

Base prefix: `/api/v1/cases`

- `POST /tendency`
  - input: mode, source_type (text/upload/case_id), filters, analysis window
  - output: tendency summary + distributions + caveats + disclaimer

Optional phase-5.5:

- `POST /tendency/batch`
- `GET /tendency/{analysis_id}` for async heavy runs

### Response essentials

- `summary_text` (historical framing only)
- `outcome_distribution`
- `sentence_distribution` (if applicable)
- `trend_analysis`
- `sample_size`
- `confidence_band`
- `key_factors`
- `limitations`
- `disclaimer`

## 8) Data and Modeling Strategy

### 8.1 Deterministic baseline (ship first)

- Build a strict cohort filter stack:
  - case type
  - court/court level
  - primary statutes/sections
  - date recency window
- Use weighted fallback relaxation when cohort is too small.
- Emit explicit warning when minimum support threshold is not met.

### 8.2 ML track (parallel)

- Candidate models:
  - Logistic Regression (baseline)
  - Random Forest
  - XGBoost or LightGBM (if dependency and data quality permit)
- Calibration:
  - Platt scaling or isotonic regression
- Metrics:
  - macro-F1, balanced accuracy, Brier score, ECE
- Store model card-style metadata for every trained artifact.

### 8.3 Explainability

- Global factors: top feature importances.
- Local factors: per-analysis top contributors.
- If SHAP not feasible in runtime, use model-native importance fallback.

## 9) Frontend Experience Plan

- Add tendency view under existing case workflow (or dedicated tab/page).
- Sections:
  - historical outcome distribution
  - sentence tendency (when applicable)
  - trend chart
  - key factors
  - confidence and limitations block
- Persistent disclaimer banner and insufficient-data warning state.

## 10) Iterative Implementation Plan

### Iteration 0 - Contracts and scaffold

- Create module skeleton and API schema contracts.
- Add contract tests.

### Iteration 1 - Deterministic baseline engine

- Implement cohort selector and stats engine.
- Return stable tendency response with disclaimer.

### Iteration 2 - Feature builder and model benchmark harness

- Implement feature extraction and offline training script.
- Produce benchmark report artifact.

### Iteration 3 - Calibration and confidence payload

- Add calibration pipeline and confidence metadata.
- Validate calibration metrics in report.

### Iteration 4 - Explainability and bias audit

- Add feature influence summaries and slice-level bias checks.
- Emit warnings for disparity/drift signals.

### Iteration 5 - Frontend dashboard

- Build tendency dashboard UI and warning states.
- Add API client/hook/types.

### Iteration 6 - Hardening and docs

- Add runbook, evaluation harness, and release checklist updates.

## 11) Testing Strategy

### Unit tests

- Cohort filter correctness and fallback behavior.
- Distribution math and confidence interval calculations.
- Calibration metric calculations.
- Disclaimer and safety framing enforcement.

### Integration tests

- API contract and response shape stability.
- Low-sample and missing-data degraded paths.
- End-to-end tendency generation from text and case_id.

### Regression tests

- Schema drift checks.
- Historical benchmark band checks for key metrics.

## 12) Risks and Mitigations

- Risk: users interpret tendency as verdict prediction.
  - Mitigation: strict wording lint + mandatory disclaimer blocks.
- Risk: sparse cohorts create misleading statistics.
  - Mitigation: minimum support thresholds + explicit insufficient-data warnings.
- Risk: class imbalance skews output.
  - Mitigation: class-weighted training, balanced metrics, calibration checks.
- Risk: hidden bias across demographic/legal slices.
  - Mitigation: slice audits and surfaced disparity warnings.

## 13) Immediate Execution Order

1. Iteration 0 + 1 (contracts + deterministic baseline MVP)
2. Iteration 3 (calibration/confidence) before broad UI rollout
3. Iteration 4 + 5 (bias/explainability + dashboard)
4. Iteration 6 hardening and sign-off docs

This order ships useful statistical insights early while preserving safety framing and extensibility.
