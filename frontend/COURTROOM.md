# Live Courtroom Workflow

The `/courtroom` frontend is an educational argument-testing workspace, not a
court decision or legal advice. It displays model-generated public explanations
and evidence references, not private chain-of-thought.

## Hearing Sequence

1. Paste case text or upload PDF, DOCX, or UTF-8 TXT (maximum 10 MiB).
2. Prosecution Counsel, Defense Counsel, Constitutional Expert, Moral Advisor,
   and Legal Analyst independently review
   the case. Each completed opinion is published immediately.
3. All roles receive the same first-round opinion snapshot and produce rebuttals.
4. A separate call drafts the conclusion from the final positions.
5. The Presiding Judge reviews the draft, original opinions, rebuttals, and case
   record. Rejection is visible and includes required changes. A verdict event
   is published only for a nondegraded, explicitly approved summary.

Both API modes and the visual UI include all five deliberating roles plus the
Presiding Judge. The Moral Advisor separates ethical tradeoffs from enforceable
law, respects constitutional rights and the presumption of innocence, and
does not recommend punishment based on moral disapproval.
Peer rubric scoring remains part of both modes, before and after rebuttals.

## PDF Input and Sample

The dossier accepts a user's PDF directly, extracts its text locally, and shows
page count, extracted character count, `[PDF page N]` markers, and warnings for
blank/scanned pages or truncated extraction. Users can inspect and correct the
extracted text before starting a hearing. No automatic OCR is performed.

Download the three-page fictional Maharashtra case from the dossier or
`/samples/indian-theft-case.pdf`. Its source is
`frontend/public/samples/indian-theft-case.pdf`; regenerate it from `nyaya-ai/`
with `python scripts/generate_courtroom_sample.py`. It is an invented case packet,
not a real judgment, and includes exhibits E1-E7, conflicting evidence, competing
positions, missing information, and questions for the agents.

## Public Explanations

Every live role submission and judicial review requests a `public_explanation`:

- `conclusion_basis`: concise public reasons for the result.
- `supporting_evidence`: source reference, quotation, relevance, and a
  server-computed `quote_verified` flag. Case quotations use `case_text`; page
  markers help navigation but are not authenticated page-provenance claims.
- `assumptions`, `counterarguments`, and `uncertainty`: separate public lists.
- `change_summary`: why the position changed or was retained during rebuttal.

These are model-generated explanations, not private chain-of-thought or a
guaranteed causal account of a model's internal computation. Quotation matching
checks a minimum-length, whitespace-normalized passage against the actual
supplied case text or retrieval excerpt. It does not verify factual truth,
admissibility, completeness, or the correctness of legal reasoning.

Missing explanations and unverified source claims remain visible. The judge
withholds approval for missing explanations, unverified quoted evidence,
missing rebuttal change reasons, or outstanding required changes. Confidence
is explicitly labeled `model_self_assessment`, not a calibrated probability.
Evidence-free explanations cannot receive source-grounded approval. Original
retrieved excerpts are retained in server-owned `source_evidence` on role
reports and carried into rebuttal and judicial quotation checks, including when
multiple excerpts use the same citation identifier.

The UI preserves the submitted case snapshot separately from later draft edits.
Export audit JSON includes that snapshot, extraction metadata, available role
reports, event explanations, peer assessments, warnings, and judicial review.
This export contains case text; handle it as sensitive information.

## Spatial Chamber and Reports

The central raised bench, opposing counsel desks, advisory table, and six blob
avatars provide the role-selection controls. Select an avatar to open its insight
panel beside the chamber (or below it on mobile). Independent opinions and shared
rebuttals remain separate; unavailable submissions show an explicit empty state.
The panel prioritizes public reasons, matched quotations, assumptions,
counterarguments, uncertainty, changed positions, and original legal excerpts.
Full submissions and timestamped activity remain available as disclosures.

GSAP/ScrollTrigger provides a short entrance transition. Motion is optional and
respects reduced-motion preferences and the chamber's Pause motion control.
Only actual active-role events trigger breathing activity, not simulated thinking.

The header's Export report PDF button downloads a paginated, text-selectable A4
report generated from the server-owned hearing snapshot. It includes initial
opinions, rebuttals, public evidence and explanations, synthesis, disagreements,
judicial review, warnings, peer assessments, and the recorded event log. In-flight
exports are labeled incomplete and not approved. Rejected, failed, cancelled,
and degraded hearings cannot appear as approved. PDF text is escaped; unsupported
font glyphs use disclosed Unicode code-point markers rather than silent loss.
The original submitted case text is available in the separate JSON audit export,
not represented as part of the server PDF's original source record. Both exports
may contain sensitive facts and should be handled accordingly.

## Configuration

Use the existing `OPENAI_API_KEY`, `EXTRACTION_MODEL` (default `gpt-4o-mini`), and
`COURTROOM_ENABLE_LIVE_LLM=true`. All courtroom roles, scoring, synthesis, and
judge review use the same OpenAI model. Request-level role/provider overrides
cannot switch models. OpenAI API access is separate from a ChatGPT subscription.
The current shared client supports the GPT-4o, GPT-4.1, GPT-4-turbo, and GPT-3.5
families. Other extraction models use GPT-4o-mini with a visible warning rather
than sending incompatible parameters to reasoning-model APIs.

The frontend uses `NEXT_PUBLIC_API_URL` for HTTP and WebSocket connections.
Restart the backend after updating Python code and restart/rebuild the frontend
after changing its public API URL. HTTP event polling backs up the WebSocket.

### Connection Refused During Upload

`POST http://localhost:8000/api/v1/courtroom/document net::ERR_CONNECTION_REFUSED`
means the browser could not reach the API, not that the PDF was unreadable.
Run the full backend from `nyaya-ai/` in a separate terminal and keep it running:

```bash
venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Wait for application startup to complete and verify `http://localhost:8000/health`
returns `{"status":"ok"}`, then select the PDF again. Initial startup may load
the search/reranking models before the server accepts requests. For a browser on
another machine, `localhost` refers to that browser's machine: use a reachable
backend URL in `frontend/.env.local`, rebuild the frontend, and configure
`CORS_ORIGINS` for the frontend's actual origin. Do not expose a development API
publicly without appropriate authentication and network controls.

## API

- `POST /api/v1/courtroom/document`: multipart `file`; returns `text`, `filename`,
  `page_count`, `extracted_characters`, `truncated`, and `warnings`.
- `POST /api/v1/courtroom/analyze`: returns a queued run ID without waiting.
- `GET /api/v1/courtroom/analysis/{id}`: partial or final report. `synthesis`,
  `judge_review`, and `transparency_dashboard` are nullable until available.
- `GET /api/v1/courtroom/analysis/{id}/status`: lifecycle and progress.
- `GET /api/v1/courtroom/analysis/{id}/report.pdf`: downloadable public PDF snapshot;
  `application/pdf`, attachment disposition, no-store; missing hearings return 404.
- `GET` or `WS /api/v1/courtroom/analysis/{id}/events`: canonical event log.
- `POST /api/v1/courtroom/analysis/{id}/cancel`: cooperative cancellation.

Original opinions are retained in `initial_role_analyses`. `role_analyses` holds
the latest positions. Rebuttals link to original opinions with `responding_to`.
Events identify actual configured or fallback providers and models.

## Limits

- Run state is in memory, suitable for a single backend process. Restarting
  loses hearings; multiple workers/replicas require a shared store and broker.
- Two hearings execute concurrently, with at most ten admitted hearings.
  Saturation returns HTTP 503.
- Cancellation prevents subsequent stages and result writes but cannot abort
  an already in-flight provider request or its cost.
- Extraction allows 120,000 characters. Model case context currently uses only
  the first 25,000, with a visible warning on longer inputs. Scanned PDFs need OCR.
- Missing live output produces a clearly degraded draft, never an approved
  verdict. Degraded hearings can be retried without reusing the degraded cache.
- Same-model role agreement is not independent validation. Human legal review
  is necessary, including verification of all facts and citations.
- Cost reporting is approximate; `max_cost_usd` is a post-run warning, not a
  hard spending cap. Live integration testing can incur OpenAI charges.

## Verification

Backend tests use mocked or disabled providers. Run from `nyaya-ai/`:

```bash
COURTROOM_ENABLE_LIVE_LLM=false venv/bin/python -m pytest tests/ -q
```

Frontend verification: `npm run lint` and `npm run build` in `frontend/`.
Browser QA exercises staged mocked responses, document intake, opinion/rebuttal
updates, judge approval/rejection, cancellation, and isolation between hearings.
