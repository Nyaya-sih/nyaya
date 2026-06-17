# Phase 5 Runbook

## Core Commands

- Run outcome tendency API locally:
  - `uvicorn src.api.main:app --host 0.0.0.0 --port 8000`
- Run full backend tests:
  - `PYTHONPATH=. ../venv/bin/pytest tests/ -q`
- Run tendency model benchmark:
  - `PYTHONPATH=. ../venv/bin/python scripts/40_benchmark_tendency_models.py`
- Run tendency quality eval harness:
  - `PYTHONPATH=. ../venv/bin/python scripts/41_eval_tendency_quality.py`

## Daily Health Checks

1. API health:
   - `curl http://localhost:8000/health`
2. Tendency endpoint smoke:
   - `curl -X POST http://localhost:8000/api/v1/cases/tendency -H "Content-Type: application/json" -d '{"source_type":"text","case_text":"..."}'`
3. Quality artifact freshness:
   - verify `data/processed/tendency_eval_report.json` is recent.

## Incident: Sparse Cohort / Low Confidence

Symptoms:
- `status=insufficient_data`
- `confidence_band.level=low`
- warnings mention sparse cohort support

Actions:
1. Expand `top_k_similar` and widen year filters.
2. Confirm DB has valid non-invalid cases in relevant profile slices.
3. Re-run tendency request and compare confidence reliability.

## Incident: Bias or Drift Flag Triggered

Symptoms:
- `bias_audit.disparity_flag=true` or `bias_audit.drift_flag=true`

Actions:
1. Review `bias_audit.slice_metrics` and `bias_audit.notes` from API response.
2. Re-run with alternate cohort windows (court/year constraints) to test stability.
3. Escalate for human review before downstream decisions.

## Incident: Modeling Regression

Symptoms:
- Benchmark report drops significantly vs prior baseline.

Actions:
1. Re-run benchmark script to confirm reproducibility.
2. Inspect class imbalance and feature distribution shifts in the report.
3. Keep API in baseline mode while investigating model path.

## Release Checklist (Phase 5)

1. `PYTHONPATH=. ../venv/bin/pytest tests/ -q`
2. `PYTHONPATH=. ../venv/bin/python scripts/40_benchmark_tendency_models.py`
3. `PYTHONPATH=. ../venv/bin/python scripts/41_eval_tendency_quality.py`
4. Verify disclaimer/caveat text in API responses is present and non-empty
5. Verify frontend tendency page renders warnings, confidence, explainability, and bias audit blocks
6. Review generated artifacts under `data/processed/`
