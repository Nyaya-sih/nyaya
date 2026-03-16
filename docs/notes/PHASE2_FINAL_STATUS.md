# Phase 2 Final Status

Date: 2026-03-16

Phase 2 engineering scope is complete for the current heuristic evaluation track, with a fully operational human-judged evaluation workflow in place.

## Gate Results

- Tests: `pytest tests/ -q` -> pass (`96 passed`)
- Index integrity: `scripts/16_verify_index_integrity.py` -> pass (`status=pass`, drift=0)
- Retrieval quality (heuristic set):
  - Precision@10 = 0.3519
  - Recall@20 = 0.4839
  - MRR@10 = 0.5671
  - nDCG@10 = 0.4103
  - Meets heuristic gate thresholds in `docs/notes/PHASE2_SLOS.md`
- Benchmark (quick profile):
  - warm default p95 = 2394.1 ms
  - warm filter-heavy p95 = 1993.3 ms
  - warm long-text p95 = 1916.9 ms
  - error rate = 0.0

## Retrieval Quality Improvements (Delivered)

- Upload query preparation now removes boilerplate and prioritizes fact/issue/reasoning-heavy segments.
- Hybrid scoring is active (vector + BM25-like lexical overlap) before reranking.
- Reranker candidate text is legal-context enriched (headnotes, statutes, sections, reasoning excerpts).
- Metadata extraction for query/candidate was improved for statutes, sections, verdict, case type, and court normalization.
- UI calibration now emphasizes practical buckets: Semantic Match, Legal Overlap, and Context Match.

## Human-Judged Evaluation Pipeline (Ready, Deferred)

Implemented and documented end-to-end workflow:

1. Generate annotation packets: `scripts/21_generate_human_eval_packets.py`
2. Split reviewer batches: `scripts/24_export_annotation_batch.py`
3. Validate annotation completeness: `scripts/23_validate_human_annotations.py`
4. Merge reviewer batches and report conflicts: `scripts/25_merge_annotator_batches.py`
5. Build human-gold dataset: `scripts/22_build_human_gold_from_packets.py`
6. Evaluate graded metrics: `scripts/17_eval_retrieval_quality.py --eval-file ...`

Execution status: prepared and kept stable for later use; active annotation can begin when lawyer reviewers are available.

Reference docs:

- `docs/notes/PHASE2_HUMAN_EVAL_PLAN.md`
- `docs/notes/PHASE2_ANNOTATOR_HANDOFF_TEMPLATE.md`
