# Phase 2 API Contracts

Base prefix: `/api/v1/cases`

## Endpoints

- `POST /similar`
  - Body: text query + optional filters (`court`, `case_type`, `year_from`, `year_to`, `verdict`, `top_k`, `similarity_mode`)
  - `similarity_mode` allowed: `combined`, `factual`, `legal`, `fulltext`
- `POST /similar/upload`
  - Multipart: file (`.pdf`/`.docx`) + same optional filter form fields
- `GET /{case_id}`
  - Returns full case details
- `GET /{case_id}/similar`
  - Query params: `top_k`, `similarity_mode`
- `POST /explain`
  - On-demand LLM explanation for query text + candidate case id
- `GET /search/filters`
  - Returns filter options for frontend dropdowns

## Shared Search Response Shape

- `query_summary`: string
- `total_results`: integer
- `search_time_ms`: float
- `results`: array
- `filters_applied`: object
- `disclaimer`: string
- `retrieval_mode`: string
  - `full`: full intended retrieval path
  - `degraded`: fallback mode (e.g., reranker unavailable)
  - `rejected`: query rejected as non-legal text
- `warnings`: string array with fallback diagnostics

## Validation Rules

- Text search minimum length: `100`
- `top_k`: `1..20`
- `year_from`, `year_to`: `1950..2025`
- Invalid `similarity_mode` is rejected with validation error

## Stability Rules

- Existing keys should not be removed without version bump.
- New keys should be additive and optional for compatibility.
- Error responses should preserve `status_code` semantics (400/404/422/500/503).
