# Courtroom Plan Progress Tracker

Source plan: `docs/plans/courtroomPlan.md`

Last reviewed: 2026-07-22

## Overall Status
- Current implementation is past the prototype stage and close to the Phase 4 target.
- Core courtroom analysis, scoring, replay, evaluation, and frontend entry point exist.
- Several items from the plan are still not implemented, especially the full session flow, judicial panel, and planned visualization layers.

## What Is Done
- Backend courtroom service is wired into the main app.
- API routes exist for courtroom analysis, status, events, cancel, and full report retrieval.
- Core analysis pipeline exists: role analysis, rebuttal, synthesis, evaluation, scoring, model routing, and cost tracking.
- WebSocket event streaming and replay/backfill are implemented.
- Frontend courtroom page exists and is mounted in navigation.
- Basic disclaimers and legal-simulation framing are present in the UI.
- Test coverage exists for API contracts and scoring utilities.
- An evaluation script and generated evaluation report exist.

## What Is Partially Done
- Live visibility is present, but runs still complete synchronously before the page replays events.
- Retrieval and model routing exist, but the flow is not yet the full upload-driven courtroom experience from the plan.
- Rebuttal is implemented as a revision pass, not the full objection/cross-examination structure described in the plan.
- Synthesis exists, but the 5-agent judicial panel and dissent tracking are not fully implemented in the runtime flow.
- The current UI shows courtroom events, but the richer CourtroomStage / Transcript / Graph / VerdictReport component set is not present.

## What Is Still Missing
- Session-based upload flow with document framing and user confirmation before trial start.
- Postgres-backed persisted courtroom sessions and migrations for courtroom run state.
- Planned endpoints for verdict, PDF report, and argument graph.
- LangGraph-based orchestration as described in the plan.
- Full 5-agent role groups and 5-agent judicial panel.
- Dedicated live courtroom visualization with stage, transcript, and argument graph views.
- Onboarding modal and stronger persistent legal-disclaimer UI.
- Generated `docs/schemas.md` from the courtroom Pydantic models.

## Important Mismatches With The Plan
- Plan expects `POST /sessions` and `GET /sessions/{id}/...`; current implementation uses `/api/v1/courtroom/analysis/{id}` style routes.
- Plan expects fully structured live events from a session pipeline; current experience is closer to execute-then-replay.
- Plan expects LangGraph orchestration; current implementation uses custom orchestration code.
- Plan expects a 5-agent judicial panel with votes and dissent; current runtime does not expose that full flow.

## Current Strengths
- The feature is real and testable end to end.
- The system already supports structured courtroom events and replay.
- The backend is modular enough to evolve toward the plan without a rewrite.
- The UI and API are integrated and visible in the app.

## Suggested Next Steps
1. Add upload/session framing flow.
2. Persist courtroom runs in PostgreSQL.
3. Implement judicial panel voting and dissent flow.
4. Replace custom orchestration with LangGraph or align the plan to the current architecture.
5. Build the courtroom visualization components.
6. Add the report and graph endpoints.

## Update Log
- 2026-07-22: Initial progress review created after repo-wide courtroom audit.
