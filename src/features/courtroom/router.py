"""FastAPI router for Phase 4 simulated courtroom."""

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from src.api.dependencies import get_courtroom_service
from src.features.courtroom.document_router import router as document_router
from src.features.courtroom.report_pdf import build_report_pdf
from src.features.courtroom.schemas import (
    CancelCourtroomAnalysisResponse,
    CourtroomAnalysisResponse,
    CourtroomAnalysisStatusResponse,
    CourtroomAnalyzeRequest,
    CreateCourtroomAnalysisResponse,
    TrialEvent,
)
from src.features.courtroom.service import (
    CourtroomCapacityError, CourtroomRunNotFoundError, CourtroomService,
)


router = APIRouter(prefix="/api/v1/courtroom", tags=["Simulated Courtroom"])


@router.post("/analyze", response_model=CreateCourtroomAnalysisResponse)
def analyze_case(
    payload: CourtroomAnalyzeRequest,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> CreateCourtroomAnalysisResponse:
    """Start a simulated courtroom analysis run."""
    try:
        return courtroom_service.create_analysis(payload)
    except CourtroomCapacityError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    "/analysis/{analysis_id}/report.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def download_analysis_report(
    analysis_id: str,
    courtroom_service: CourtroomService = Depends(get_courtroom_service),
) -> Response:
    """Download the canonical public snapshot, including incomplete runs."""
    try:
        report = courtroom_service.get_analysis(analysis_id)
    except CourtroomRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", report.analysis_id)[:120] or "analysis"
    return Response(
        content=build_report_pdf(report),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="courtroom-{safe_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


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

        while True:
            current_run = courtroom_service.store.get_run(analysis_id)
            if current_run and current_run.status in {"completed", "degraded", "failed", "cancelled"}:
                # Drain persisted history too: completion may race the initial replay.
                for pending in courtroom_service.get_trial_events(analysis_id):
                    if pending["event_id"] not in sent_event_ids:
                        await websocket.send_json(pending)
                        sent_event_ids.add(pending["event_id"])
                await websocket.close()
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
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


courtroom_router = router
router = APIRouter()
router.include_router(courtroom_router)
router.include_router(document_router)
