# AI-Simulated Indian Courtroom — Build Plan

## 0. Project Summary

Build a system where a user uploads case documents (FIR, charge sheet, witness statements, evidence
descriptions, etc.) and the system runs a **fully orchestrated, multi-agent courtroom simulation**:
multiple LLM instances play distinct legal roles (Prosecution, Defense, Constitutional/Procedural
Expert, Investigative/Forensic Analyst), argue and rebut each other in structured rounds, and a
5-agent **Judicial Panel** deliberates to a final verdict with a confidence score. The entire process
must be **fully visible to the user in real time** — no hidden black-box steps.

This is a simulation/education tool, not a legal-advice product. That framing must be visible in the
UI (disclaimer banner, footer, and onboarding modal).

---

## 1. Tech Stack

- **Backend**: Python 3.11+, FastAPI, WebSockets (native `fastapi.WebSocket`, no extra broker needed at MVP scale)
- **Orchestration**: LangGraph (state machine / graph execution) — chosen because the pipeline has
  parallel branches (role groups), join points (rebuttal needs all group outputs), and conditional
  loops (extra deliberation rounds if disagreement is high)
- **Persistence**: PostgreSQL (session state, structured trial record) + optional Neo4j later for the
  argument graph (start with a JSON adjacency structure in Postgres; migrate to Neo4j only if graph
  queries become a bottleneck — don't over-engineer at MVP)
- **Frontend**: React + TypeScript, Vite, Tailwind, D3.js (argument graph), Framer Motion (courtroom
  stage animations)
- **Model providers (free-tier)**: Google AI Studio (Gemini 2.x Flash), Groq (Llama 3.x / Mixtral),
  OpenRouter (rotating free-tagged models), Mistral (free tier), OpenAI (trial credits only —
  treat as optional/best-effort, not load-bearing)
- **Queue/rate-limit handling**: `asyncio` semaphores per provider + exponential backoff; no external
  queue system needed at MVP scale

---

## 2. Repository Structure

```
/backend
  /adapters/           # one file per model provider, common interface
  /orchestrator/        # LangGraph state machine, stage definitions
  /agents/              # role prompt templates, agent config
  /models/              # Pydantic schemas for all structured events
  /api/                 # FastAPI routes + websocket handlers
  /db/                  # Postgres models, migrations
  /services/            # doc ingestion, confidence scoring, moderator logic
  main.py
/frontend
  /src
    /components/
      CourtroomStage/    # seat layout, speaking indicators, confidence meters
      Transcript/        # live scrolling structured log
      ArgumentGraph/      # D3 force-directed claim/rebuttal graph
      UploadFlow/
      VerdictReport/
    /hooks/
      useTrialSocket.ts  # websocket subscription + event reducer
    /store/              # trial state store (Zustand or Redux)
/docs
  plan.md               # this file
  schemas.md            # generated from Pydantic models
```

---

## 3. Core Data Model (all inter-agent + UI events are structured JSON — nothing is free-text-only)

Define these as Pydantic models in `/backend/models/`. Every single agent output, regardless of
stage, is an instance of `TrialEvent`. The frontend renders purely off a stream of `TrialEvent`
objects — this is what makes the "not a black box" requirement work.

```python
class TrialEvent(BaseModel):
    event_id: str
    session_id: str
    stage: Literal["ingestion","group_deliberation","rebuttal","judicial","verdict"]
    role: str                 # "prosecution", "defense", "constitutional_expert",
                               # "investigative_analyst", "judge_panel", "moderator"
    agent_id: str              # which of the 5 in the group, or "supervisor"
    model_provider: str
    model_id: str
    round: int
    event_type: Literal["position","revision","objection","rebuttal","synthesis","vote","verdict"]
    content: str                # the argument/reasoning text
    responding_to: Optional[str] # event_id this responds to, for rebuttal chains
    citations: List[Citation]    # references to uploaded doc sections
    confidence: float            # 0.0-1.0, self-reported
    timestamp: datetime

class Citation(BaseModel):
    doc_id: str
    section_ref: str
    quoted_text: Optional[str]   # short excerpt only

class GroupSynthesis(BaseModel):
    role: str
    final_argument: str
    key_evidence_cited: List[Citation]
    raw_confidence: float         # supervisor's self-reported number
    agreement_ratio: float        # fraction of 5 agents that converged
    weighted_confidence: float    # raw_confidence * agreement_ratio
    dissent_notes: List[str]

class VerdictRecord(BaseModel):
    verdict: str
    reasoning: str
    charges_analysis: List[ChargeFinding]
    judge_votes: List[JudgeVote]   # one per panel member, for dissent display
    overall_confidence: float
    procedural_flags: List[str]

class JudgeVote(BaseModel):
    agent_id: str
    model_id: str
    position: str
    confidence: float
    is_dissent: bool
```

**Rule for Codex**: never let an agent's raw text response go directly to the frontend. Always parse
into one of the above schemas (use structured output / JSON mode on every model call — see Section 6).

---

## 4. Pipeline Stages — Detailed Spec

### Stage 0 — Ingestion & Case Framing

- Accept file uploads (PDF, DOCX, images with OCR fallback, plain text).
- Extract text, chunk by logical section (FIR details, charges, witness statements, evidence list).
- Store each chunk with a stable `doc_id` + `section_ref` so agents can cite precisely.
- Run one lightweight "case framing" model call to produce: case summary, list of charges/sections
  of law implicated, list of parties. Show this to the user as a confirmation step before the trial
  starts (human-in-the-loop checkpoint — user can correct/add before proceeding).

### Stage 1 — Parallel Role-Group Deliberation

Groups run **concurrently** (this is a fan-out in the LangGraph):

- Prosecution Group (5 agents)
- Defense Group (5 agents)
- Constitutional/Procedural Expert Group (5 agents)
- Investigative/Forensic Analyst Group (5 agents)

Within each group, run this sub-protocol:

1. **Round 1 (parallel)**: each of the 5 agents independently receives the case packet + role-specific
   system prompt, returns a `position` TrialEvent with citations + confidence.
2. **Round 2 (parallel)**: each agent receives the other 4 positions from round 1, returns a `revision`
   event (agree/disagree/refine).
3. **Disagreement check**: compute variance across confidence scores and semantic divergence
   (simple heuristic at MVP: keyword/stance clustering, or a cheap classifier call). If above
   threshold, run **Round 3**; otherwise skip.
4. **Synthesis**: the group's designated supervisor agent reads all rounds and produces a
   `GroupSynthesis`. Compute `agreement_ratio` programmatically (not model-reported) by clustering
   the 5 final stances (e.g. embedding similarity or simple majority-position matching) — do not
   trust a model's self-assessment of "how much we agreed."

Model assignment: rotate models across roles per session so no provider consistently plays "defense"
etc. Store the rotation seed for reproducibility.

### Stage 2 — Cross-Role Rebuttal (the "live courtroom")

This is turn-based, not parallel. A lightweight **Moderator** component (can be rule-based, not an
LLM call, to save quota) manages the queue:

```
1. Opening: Prosecution supervisor statement → Defense supervisor statement
2. Evidence phase: Investigative Analyst supervisor presents findings
3. Objection phase: Constitutional/Procedural supervisor may interject at any point
   (flags inadmissibility / procedural violation — tagged as event_type="objection")
4. Cross-examination: N rounds of Prosecution ↔ Defense, each event's `responding_to`
   field must reference a specific prior claim's event_id
5. Closing: Prosecution → Defense
```

Moderator responsibilities (implement as deterministic Python logic, not an LLM):

- Enforce turn order.
- Detect repetition/no new information across 2 consecutive rounds (simple similarity check) and
  cut the phase early.
- Cap total rounds per phase (configurable, default 3) to bound API usage.

### Stage 3 — Judicial Panel Deliberation

5-agent judge group. Distinct from the role groups above — should use models NOT heavily represented
in the role groups for that session, if possible, to reduce correlated bias.

1. Each judge independently receives the **full structured trial record** (all TrialEvents from
   Stages 1–2, not raw documents) and drafts an independent verdict + reasoning + confidence.
2. Judges see each other's drafts, may revise once.
3. Aggregate via **explicit vote**, not narrative summary: majority position wins; anyone who
   disagrees is recorded as a `JudgeVote` with `is_dissent=True` and displayed as a dissenting
   opinion, not discarded.
4. Panel supervisor writes final `VerdictRecord`, but the numeric `overall_confidence` is computed
   programmatically as a function of vote agreement + individual confidences, not self-reported.

### Stage 4 — Verdict Synthesis + Rendering

- Compile final `VerdictRecord` + full session TrialEvent log into a downloadable report (PDF via the
  pdf skill, or structured HTML).
- Persist full session so user can replay it later (scrub through the timeline).

---

## 5. Orchestration Engine (LangGraph state machine)

Model the graph as:

```
ingestion_node
   → fan_out: [prosecution_group, defense_group, constitutional_group, investigative_group]
   → join: rebuttal_node (waits for all 4 group syntheses)
   → judicial_panel_node
   → verdict_node
```

Each `*_group` node is itself a sub-graph implementing the Round 1 → Round 2 → [conditional Round 3]
→ Synthesis sequence described above. Use LangGraph's conditional edges for the disagreement-based
loop.

Every node, on completion of each internal step, should:

1. Persist the `TrialEvent`(s) to Postgres.
2. Push the event(s) over the session's WebSocket channel immediately (don't batch at the end of a
   node — the whole point is live visibility).

---

## 6. Model Adapter Layer

Single common interface so any provider can fill any "agent slot":

```python
class ModelAdapter(Protocol):
    async def generate(
        self,
        system_prompt: str,
        messages: List[dict],
        response_schema: Type[BaseModel],   # enforce structured output
        temperature: float = 0.7,
    ) -> BaseModel: ...
```

- Implement one adapter per provider (`gemini_adapter.py`, `groq_adapter.py`, `openrouter_adapter.py`,
  `mistral_adapter.py`, `openai_adapter.py`).
- Use each provider's native JSON-mode / structured-output feature where available; otherwise
  prompt for JSON-only output and parse defensively (strip code fences, retry once on parse failure).
- Wrap every call in retry + exponential backoff; on repeated failure, **fail over to a different
  model** in the pool for that agent slot rather than failing the whole session, and log/flag this
  substitution in the TrialEvent (`model_id` field reflects the actual model used, plus a
  `fallback_used: bool` field).
- Rate limiting: `asyncio.Semaphore` per provider, sized to that provider's known free-tier RPM.
  Central `services/rate_limiter.py`.
- Config-driven agent-to-model mapping (YAML or DB row) so a session can be re-run with a different
  model roster without code changes:

```yaml
agent_pool:
  - {slot: prosecution_1, provider: gemini, model: gemini-2.0-flash}
  - {slot: prosecution_2, provider: groq, model: llama-3.3-70b}
  ...
```

---

## 7. Visualization — This Is the Product's Differentiator

Build three concurrent, synchronized views, all driven by the same live `TrialEvent` WebSocket stream.
A single `useTrialSocket` hook maintains an ordered event log in a client-side store; all three
components subscribe to the same store so they stay in sync without extra round-trips.

### 7.1 Courtroom Stage View

- Visual "seats" for each role: Prosecution, Defense, Constitutional Expert, Investigative Analyst,
  Judicial Panel — laid out like an actual courtroom (judge panel at top/center, prosecution/defense
  facing each other).
- Each seat shows: role label, a **speaking indicator** (animated pulse/glow when that role has an
  active/streaming event), and a **live confidence meter** (small gauge or bar, updates as the
  group's `weighted_confidence` changes across rounds).
- During Stage 1 (parallel group deliberation), show all 4 non-judge seats "thinking" simultaneously
  with a subtle internal-agent indicator (5 small dots per seat, filling in as each of the 5 agents
  in that group responds).
- During Stage 2 (rebuttal), animate turn-taking explicitly — highlight whichever seat currently
  has the floor, dim others.
- During Stage 3, all 5 judge seats "light up" and a vote tally visual builds up (e.g. 5 small
  gavel icons that fill in as each judge casts a position), ending in a clear majority/dissent
  visualization.

### 7.2 Live Transcript / Timeline

- Scrolling structured log, chronologically ordered by `TrialEvent.timestamp`.
- Each entry: role badge, round number, one-line summary of `content`, confidence badge.
- **Collapsible by default** — clicking an entry expands to show the full reasoning text and its
  citations. This satisfies "not a black box" without overwhelming the default view: nothing is
  hidden, it's just progressively disclosed.
- For group deliberation stages, nest the 5 individual agent responses under the group's synthesis
  entry (tree/accordion), so a user can drill from "Prosecution's final argument" down into "why
  each of the 5 models landed there."
- Filter controls: by role, by stage, by event_type (e.g. show only objections).

### 7.3 Argument Graph (D3 force-directed)

- Nodes = individual claims/positions (one node per meaningful `TrialEvent`).
- Edges = `responding_to` relationships — a rebuttal edge, an objection edge, a supporting-citation
  edge (different edge colors/styles per relationship type).
- Node color = role (consistent color coding across all 3 views — define a shared color token map
  in `/frontend/src/theme/roles.ts` used everywhere).
- Node size = confidence.
- Clicking a node highlights its full chain (what it responded to, and what responded to it) and
  syncs the transcript view to scroll to that entry.
- This view is most useful post-trial for "how did we get to this verdict" exploration, but should
  also build live during the trial, not just appear at the end.

### 7.4 Shared design requirements

- All three views subscribe to one WebSocket event stream — never poll, never have views get out of
  sync with each other.
- Persist full event history per session so a completed trial can be **replayed** with a scrubber
  (timeline slider), not just viewed live.
- Loading/thinking states must be honest — if a group is on Round 2, say "Round 2 of up to 3" rather
  than a vague spinner, since transparency about process state is part of the product's value prop.

---

## 8. API Surface (FastAPI)

```
POST   /sessions                     # create session, upload docs, returns session_id
GET    /sessions/{id}/case-summary   # Stage 0 output, for user confirmation
POST   /sessions/{id}/confirm        # user confirms case framing, triggers pipeline start
WS     /sessions/{id}/events         # live TrialEvent stream
GET    /sessions/{id}/events         # full event history (for replay / page refresh recovery)
GET    /sessions/{id}/verdict        # final VerdictRecord
GET    /sessions/{id}/report.pdf     # downloadable report
GET    /sessions/{id}/graph          # argument graph as nodes/edges JSON
```

WebSocket reconnection: on reconnect, client calls `GET /sessions/{id}/events` to backfill missed
events before resubscribing live — never lose transcript continuity on a dropped connection.

---

## 9. Build Order / Milestones (for Codex to work through sequentially)

**Milestone 1 — Foundations**

- Repo scaffold, Pydantic schemas, Postgres models + migrations.
- Model adapter layer for 2 providers only (Gemini + Groq) to start.
- Basic doc ingestion (PDF/text extraction, chunking).

**Milestone 2 — Single-Group Deliberation (prove the core loop)**

- Implement just the Prosecution group: Round 1 → Round 2 → Synthesis, with real API calls.
- WebSocket streaming of events working end-to-end to a minimal frontend (plain transcript, no
  fancy visuals yet).

**Milestone 3 — Full Stage 1 (all 4 groups in parallel)**

- LangGraph fan-out for all 4 role groups.
- Reduce agent count to 3 per group initially if rate limits bite; make it config-driven so it's
  trivial to scale to 5 later.

**Milestone 4 — Stage 2 Rebuttal**

- Moderator logic, turn-based cross-role exchange, objection handling.

**Milestone 5 — Stage 3 + 4 Judicial Panel and Verdict**

- Judge panel deliberation, vote aggregation, dissent handling, VerdictRecord + PDF report.

**Milestone 6 — Visualization Layer**

- Courtroom Stage View, then Transcript View, then Argument Graph, in that order (stage view is
  highest-impact for the "watch it happen" feel; graph view is the most complex, do it last).
- Wire up replay/scrubber.

**Milestone 7 — Hardening**

- Failover between providers, rate-limit tuning, session persistence/resume on crash,
  reproducibility (seeded model rotation), basic auth if this becomes multi-user.

Build and demo-test after every milestone — don't let Codex build all stages before any visualization
exists; the visual feedback loop is what lets you sanity-check the agent behavior early.

---

## 10. Guardrails for Codex

- Every agent call must request structured output matching a Pydantic schema — never accept
  free-text-only responses that get parsed with regex.
- Confidence numbers displayed to the user must always be the **computed** (agreement-weighted)
  values, never a raw model self-report, per Section 3–4.
- The moderator/turn-management logic in Stage 2 should be deterministic Python, not an LLM call —
  save API quota for actual legal reasoning.
- Cap rounds everywhere (configurable, sane defaults: 2–3 rounds per group, 3 rounds per rebuttal
  phase) to keep a single trial run under ~100 model calls at 5 agents/group; document the expected
  call count in a comment near the config so cost/quota impact is visible.
- Never expose raw uploaded document text to the frontend beyond short citation excerpts — full case
  docs stay backend-side.
- UI must carry a persistent, unmissable "this is a simulation, not legal advice" disclaimer.
- Every model call, success or failure, gets logged with provider/model/latency/token-estimate for
  later cost/performance analysis.
