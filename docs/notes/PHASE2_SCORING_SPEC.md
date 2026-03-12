# Phase 2 Scoring Spec

This document freezes the similarity scoring behavior for Phase 2.

## Candidate Generation

- Vector search returns top `VECTOR_SEARCH_CANDIDATES` candidates from the selected collection.
- Collection is selected by `similarity_mode`:
  - `combined` -> combined collection (or full-text collection when enabled and available)
  - `factual` -> factual collection
  - `legal` -> legal collection
  - `fulltext` -> full-text collection (fallback to combined if unavailable)

## Reranking

If reranking is enabled (`ENABLE_RERANKING=true`):

1. Cross-encoder predicts raw relevance score for each `(query, candidate)` pair.
2. Raw scores are min-max normalized to `[0, 1]`.
3. Final score is computed as:

```text
combined_score = vector_weight * vector_score + model_weight * rerank_score
```

Where:

- `vector_weight` comes from `RERANKER_VECTOR_WEIGHT`
- `model_weight` comes from `RERANKER_MODEL_WEIGHT`
- weights are normalized internally so they sum to `1.0`

If both configured weights are `0`, defaults are used (`0.3`, `0.7`).

If reranking is disabled, `combined_score == vector_score`.

## Thresholding

- Final candidates are filtered by `SIMILARITY_THRESHOLD` against `combined_score`.
- Candidates below threshold are excluded from API response.

## Deterministic Tie-Break

When candidates have close/equal scores, ordering is stabilized with this sort key:

1. `combined_score` (desc)
2. `rerank_score` (desc)
3. `vector_score` (desc)
4. `case_id` (asc)

This prevents non-deterministic rank swaps across runs.
