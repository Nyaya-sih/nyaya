"""FastAPI router for Phase 4 simulated courtroom."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi import WebSocket, WebSocketDisconnect

from src.api.dependencies import get_courtroom_service
from src.features.courtroom.schemas import (
    CancelCourtroomAnalysisResponse,
    CourtroomAnalysisResponse,
    CourtroomAnalysisStatusResponse,
    CourtroomAnalyzeRequest,
    CreateCourtroomAnalysisResponse,
    TrialEvent,
)
from src.features.courtroom.service import CourtroomRunNotFoundError, CourtroomService


router = APIRouter(prefix="/api/v1/courtroom", tags=["Simulated Courtroom"])


@router.post("/analyze", response_model=CreateCourtroomAnalysisResponse)
def analyze_case(
    payload: CourtroomAnalyzeRequest,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CreateCourtroomAnalysisResponse:
    """Start a simulated courtroom analysis run."""
    return courtroom_service.create_analysis(payload)


@router.get("/analysis/{analysis_id}", response_model=CourtroomAnalysisResponse)
def get_analysis(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CourtroomAnalysisResponse:
    """Get full courtroom report by analysis id."""
    try:
        return courtroom_service.get_analysis(analysis_id)
    except CourtroomRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/analysis/{analysis_id}/status",
    response_model=CourtroomAnalysisStatusResponse,
)
def get_analysis_status(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CourtroomAnalysisStatusResponse:
    """Get status/progress for courtroom run."""
    try:
        return courtroom_service.get_status(analysis_id)
    except CourtroomRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/analysis/{analysis_id}/cancel",
    response_model=CancelCourtroomAnalysisResponse,
)
def cancel_analysis(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CancelCourtroomAnalysisResponse:
    """Cancel a running courtroom analysis if possible."""
    try:
        return courtroom_service.cancel_analysis(analysis_id)
    except CourtroomRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/analysis/{analysis_id}/events", response_model=list[TrialEvent])
def get_analysis_events(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> list[TrialEvent]:
    """Get the persisted trial event log for a courtroom analysis."""
    if courtroom_service.store.get_run(analysis_id) is None:
        raise HTTPException(status_code=404, detail="Courtroom analysis not found.")
    return [TrialEvent.model_validate(item) for item in courtroom_service.get_trial_events(analysis_id)]


@router.websocket("/analysis/{analysis_id}/events")
async def stream_analysis_events(
    websocket: WebSocket,
    analysis_id: str,
) -> None:
    """Stream courtroom events and replay existing history on connect."""
    await websocket.accept()

    courtroom_service = getattr(websocket.app.state, "courtroom_service", None)
    if courtroom_service is None:
        await websocket.close(code=4503)
        return

    run = courtroom_service.store.get_run(analysis_id)
    if run is None:
        await websocket.close(code=4404)
        return

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    subscription = courtroom_service.event_broker.subscribe(analysis_id, queue, loop)
    sent_event_ids: set[str] = set()

    try:
        for event in courtroom_service.get_trial_events(analysis_id):
            event_id = str(event.get("event_id", ""))
            if event_id:
                sent_event_ids.add(event_id)
            await websocket.send_json(event)

        current_run = courtroom_service.store.get_run(analysis_id)
        if current_run and current_run.status in {"completed", "degraded", "failed", "cancelled"}:
            await websocket.close()
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                current_run = courtroom_service.store.get_run(analysis_id)
                if current_run and current_run.status in {"completed", "degraded", "failed", "cancelled"}:
                    break
                continue

            event_id = str(event.get("event_id", ""))
            if event_id and event_id in sent_event_ids:
                continue
            if event_id:
                sent_event_ids.add(event_id)
            await websocket.send_json(event)

    except WebSocketDisconnect:
        return
    finally:
        courtroom_service.event_broker.unsubscribe(subscription)
