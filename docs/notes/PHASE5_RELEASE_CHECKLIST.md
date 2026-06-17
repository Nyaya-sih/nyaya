# Phase 5 Release Checklist

Use this checklist before marking Phase 5 production-ready.

## Quality Gates

- [x] Backend test suite passes (`PYTHONPATH=. ../venv/bin/pytest tests/ -q`)
- [x] Frontend lint passes (`npm run lint` from `frontend/`)
- [x] Tendency benchmark report generated (`data/processed/tendency_benchmark_report.json`)
- [x] Tendency eval report generated (`data/processed/tendency_eval_report.json`)

### Quantitative Acceptance Targets (Initial)

- Benchmark (`data/processed/tendency_benchmark_report.json`):
  - [x] `benchmark.status == "ok"`
  - [x] `benchmark.sample_size >= 1000`
  - [x] best model `macro_f1 >= 0.25`
  - [x] best model `accuracy >= 0.55`
  - [x] best model `brier <= 0.10`
- Eval harness (`data/processed/tendency_eval_report.json`):
  - [x] `completion_rate == 1.0`
  - [x] `insufficient_data_rate <= 0.25`
  - [x] `avg_sample_size >= 150`
  - [x] `avg_confidence_reliability >= 0.40`
  - [x] `drift_flag_rate <= 0.40` (currently `0.00`)

## API Contract and Safety

- [x] `POST /api/v1/cases/tendency` returns required payload blocks:
  - [x] `outcome_distribution`
  - [x] `confidence_band`
  - [x] `confidence_notes`
  - [x] `explainability_signals`
  - [x] `bias_audit`
  - [x] `limitations`
  - [x] `disclaimer`
- [x] Output framing is historical tendency, not verdict prediction
- [x] Low-sample paths emit warnings and/or `insufficient_data`

## Frontend Readiness

- [x] `/tendency` route available in navbar
- [x] Input supports text and case-id source types
- [x] Warning/caveat/disclaimer blocks are visible in report view
- [x] Confidence and bias-audit fields render correctly

## Operational Readiness

- [x] Runbook exists and is current (`docs/notes/PHASE5_RUNBOOK.md`)
- [x] Team can run benchmark/eval scripts end-to-end
- [x] Known limitations and caveats are documented in status notes
