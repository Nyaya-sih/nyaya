# changesByOc

Phase 2 change tracker (one/two-line per iteration).

1. `97a2261c` - Hardened scoring and search mode behavior; added scoring config knobs and deterministic reranker tie-break ordering.
2. `81cbf6d2` - Strengthened similarity explanation grounding by normalizing legal terms/courts and tightening explanation claims.
3. `56182e2f` - Enforced API contract validation for similar search (mode literals, request bounds, schema-level checks).
4. `23b99734` - Added regression + integrity + eval tooling foundations (`16_verify_index_integrity.py`, `17_eval_retrieval_quality.py`, new tests).
5. `46e56ac6` - Expanded benchmark scenarios and created initial eval dataset template scaffold.
6. `af35e79c` - Added degraded-mode metadata/warnings in search responses and documented API/SLO/runbook docs.
7. `08837beb` - Synced frontend with backend mode semantics (`fulltext` option + degraded/warning UX cards in results).
8. `2eae5a12` - Made embedding scripts non-interactive/ops-friendly using `--yes` and `--batch-size` CLI flags.
9. `42693cc7` - Improved gate script reliability (`--quick` benchmark mode + HTTP fallback for Qdrant integrity counts).
10. `77b9339b` - Defaulted query LLM metadata extraction to off to reduce default latency overhead.
11. `cd9d692c` - Synced vector index with DB, rebuilt manifest, expanded eval dataset generation, and tuned reranker candidate path.
12. (current, uncommitted) - Improved `/cases/{id}/similar` to apply case-context filters (`case_type`, `verdict`, year window) and added endpoint contract test coverage.
13. (current, uncommitted) - Added this running tracker file for Phase 2 visibility as requested.
14. (current, uncommitted) - Added a final broad fallback pass for `/cases/{id}/similar` (strict -> medium -> loose -> broad) to reduce no-result queries while preserving earlier precision tiers.
15. (current, uncommitted) - Regenerated eval dataset and reran gates (`pytest`, index integrity, benchmark, retrieval eval) to refresh latest Phase 2 status artifacts.
16. (current, uncommitted) - Increased case-to-case retrieval recall by using larger candidate pools for `/cases/{id}/similar` and adding mode fallback (`fulltext` -> `combined`) when strict fulltext path returns empty.
17. (current, uncommitted) - Focused case query construction on title/headnotes/sections/reasoning/full-text excerpt (reduced noisy argument fields) and expanded API contract tests for new fallback behavior.
18. (current, uncommitted) - Updated Phase 2 quality SLO/checklist docs to separate heuristic-dataset release gates from stricter human-judged production targets.
19. (current, uncommitted) - Added a concrete human-judged eval plan doc (sampling, annotation protocol, JSONL schema, graded-metric usage) and linked it from the execution checklist.
20. (current, uncommitted) - Extended retrieval eval script to support configurable input/output paths and graded human-judgment labels (`judgments` with 0/1/2) for nDCG and relevance metrics.
21. (current, uncommitted) - Added `scripts/21_generate_human_eval_packets.py` plus tests to build reviewer-ready annotation packets from live `/cases/{id}/similar` results.
22. (current, uncommitted) - Generated initial annotation packet batch at `data/evals/similar_cases_human_packets.jsonl` and updated the human eval plan with the exact generation command.
23. (current, uncommitted) - Added `scripts/22_build_human_gold_from_packets.py` and tests to convert labeled annotation packets into `similar_cases_human_gold.jsonl` for graded evaluation runs.
24. (current, uncommitted) - Added `scripts/23_validate_human_annotations.py` and tests to report annotation completeness/label distribution before converting packets into human-gold eval data.
25. (current, uncommitted) - Added `docs/notes/PHASE2_ANNOTATOR_HANDOFF_TEMPLATE.md` and linked it from human-eval/checklist docs so reviewers can start labeled batches with a repeatable QA/sign-off flow.
