# Phase 2 Annotator Handoff Template

Use this template to start a new annotation batch for human-judged retrieval evaluation.

## Batch Metadata

- Batch ID: `YYYY-MM-DD-<team>-<n>`
- Packets file: `data/evals/similar_cases_human_packets.jsonl`
- Assigned query range/count:
- Similarity mode used for packet generation:
- Top-k candidates per query:
- Annotation start date:
- Annotation due date:

## Reviewer Assignments

- Reviewer A:
  - query_ids:
- Reviewer B:
  - query_ids:
- Reviewer C:
  - query_ids:

## Label Policy (Required)

- `2` Highly relevant
  - Same core legal issue and strong factual overlap; likely useful precedent.
- `1` Partially relevant
  - Related legal issue or context, but weaker factual/legal overlap.
- `0` Not relevant
  - Different legal issue/fact pattern; unlikely to assist this query.

## Annotation Rules

1. Label at least 3 candidates per query (recommended 5+).
2. Add a short `note` for every label `1` or `2`.
3. For ambiguous candidates, pick the lower-confidence label and explain why.
4. Do not leave labels as free text; use only `0/1/2`.
5. Preserve packet structure; edit only `label` and `note` fields.

## QA Workflow

1. Run completeness check:
   - `PYTHONPATH=. venv/bin/python scripts/23_validate_human_annotations.py --min-labeled-per-query 3`
2. Resolve all queries flagged with under-labeling.
3. Convert labeled packets to gold file:
   - `PYTHONPATH=. venv/bin/python scripts/22_build_human_gold_from_packets.py --min-judgments 3`
4. Run retrieval metrics on human gold:
   - `PYTHONPATH=. venv/bin/python scripts/17_eval_retrieval_quality.py --eval-file data/evals/similar_cases_human_gold.jsonl --output-file data/processed/retrieval_eval_human_report.json`

## Conflict Resolution (10% Overlap)

- Overlap sample size:
- Conflicting query_ids:
- Adjudicator:
- Adjudication date:
- Final decisions logged:

## Batch Sign-Off

- Completeness report path:
- Human gold file path:
- Human eval report path:
- Notes/risks:
- Approved by:
