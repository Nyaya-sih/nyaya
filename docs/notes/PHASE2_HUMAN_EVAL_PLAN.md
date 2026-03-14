# Phase 2 Human-Judged Evaluation Plan

This plan upgrades retrieval quality validation from heuristic labels to human-reviewed relevance judgments.

## Objective

- Produce a human-judged gold set for similar-case retrieval.
- Measure production quality against stricter thresholds in `docs/notes/PHASE2_SLOS.md`.

## Scope

- Query set size: 300 cases (minimum 200).
- Candidate depth per query: top 20 retrieved.
- Annotation labels:
  - `2` = highly relevant precedent
  - `1` = partially relevant / contextually useful
  - `0` = not relevant

## Sampling Strategy

1. Stratify by major case types (Criminal, Civil, Writ, others).
2. Stratify by major courts to avoid single-court bias.
3. Include a mix of recent and older judgments.
4. Keep a fixed seed and preserve sampled `query_case_id`s in source control.

## Annotation Protocol

1. For each query case, review query metadata and summary excerpt.
2. Evaluate each retrieved candidate independently.
3. Label relevance (`0/1/2`) and add a short rationale.
4. Resolve disagreements via second reviewer for a 10% overlap set.
5. Record adjudicated final label.

Use `docs/notes/PHASE2_ANNOTATOR_HANDOFF_TEMPLATE.md` for batch assignment, QA steps, and sign-off tracking.

## Output Format

Store as JSONL at `data/evals/similar_cases_human_gold.jsonl`.

Create reviewer packets from current eval set using:

```bash
PYTHONPATH=. venv/bin/python scripts/21_generate_human_eval_packets.py --queries 150 --top-k 20 --similarity-mode fulltext
```

This generates `data/evals/similar_cases_human_packets.jsonl` with query context and candidate slots (`label`, `note`) for annotation.

Optionally split packets into reviewer-specific batch files:

```bash
PYTHONPATH=. venv/bin/python scripts/24_export_annotation_batch.py --reviewers A,B,C --overlap-percent 10
```

After reviewer labeling, merge batches and inspect conflicts:

```bash
PYTHONPATH=. venv/bin/python scripts/25_merge_annotator_batches.py
```

After reviewers complete labels, build final gold file using:

```bash
PYTHONPATH=. venv/bin/python scripts/22_build_human_gold_from_packets.py --min-judgments 3
```

This writes `data/evals/similar_cases_human_gold.jsonl`, ready for `scripts/17_eval_retrieval_quality.py --eval-file ...`.

Before conversion, validate annotation completeness with:

```bash
PYTHONPATH=. venv/bin/python scripts/23_validate_human_annotations.py --min-labeled-per-query 3
```

This writes `data/processed/human_annotation_report.json` with completion ratio, label distribution, and gaps.

Example record:

```json
{"query_id":"case_1234","query_case_id":1234,"similarity_mode":"fulltext","judgments":[{"case_id":4567,"label":2,"note":"Same statute + near-identical fact pattern"},{"case_id":8910,"label":1,"note":"Same court and issue but weaker factual overlap"}]}
```

## Metrics

- nDCG@10 with graded relevance (0/1/2)
- Recall@20 using labels >= 1 as relevant
- Precision@10 using labels >= 1 as relevant
- MRR@10 using labels >= 1 as relevant

## Release Usage

- Use heuristic gate for continuous iteration.
- Use human-judged gate for production sign-off.
- Keep both reports for trend comparison release-over-release.
