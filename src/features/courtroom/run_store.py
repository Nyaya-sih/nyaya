"""In-memory run store for courtroom analyses."""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional
from uuid import uuid4


@dataclass
class StoredCourtroomRun:
    """Stored courtroom run state and report fragments."""

    analysis_id: str
    mode: str
    include_rebuttal: bool
    input_source: str
    input_ref: Optional[str]
    run_key: Optional[str] = None
    status: str = "queued"
    stage: str = "queued"
    progress_percent: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    role_analyses: list[dict[str, Any]] = field(default_factory=list)
    initial_role_analyses: list[dict[str, Any]] = field(default_factory=list)
    judge_review: Optional[dict[str, Any]] = None
    evaluation_breakdown: list[dict[str, Any]] = field(default_factory=list)
    rebuttal_changes: list[str] = field(default_factory=list)
    synthesis: dict[str, Any] = field(default_factory=dict)
    transparency_dashboard: dict[str, Any] = field(default_factory=dict)
    trial_events: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class InMemoryCourtroomRunStore:
    """Thread-safe in-memory store for courtroom analysis runs."""

    def __init__(self):
        self._runs: dict[str, StoredCourtroomRun] = {}
        self._cache: dict[str, str] = {}
        self._lock = Lock()

    def create_run(
        self,
        mode: str,
        include_rebuttal: bool,
        input_source: str,
        input_ref: Optional[str],
        run_key: Optional[str] = None,
    ) -> StoredCourtroomRun:
        """Create and store a new courtroom run."""
        run = StoredCourtroomRun(
            analysis_id=f"crt_{uuid4().hex}",
            mode=mode,
            include_rebuttal=include_rebuttal,
            input_source=input_source,
            input_ref=input_ref,
            run_key=run_key,
        )
        with self._lock:
            self._runs[run.analysis_id] = run
        return run

    def get_cached_completed(self, run_key: str) -> Optional[StoredCourtroomRun]:
        """Return cached completed/degraded run for deterministic run key."""
        with self._lock:
            analysis_id = self._cache.get(run_key)
            if not analysis_id:
                return None
            run = self._runs.get(analysis_id)
            if run is None:
                return None
            if run.status != "completed":
                return None
            return deepcopy(run)

    def get_run(self, analysis_id: str) -> Optional[StoredCourtroomRun]:
        """Fetch a run by analysis id."""
        with self._lock:
            return deepcopy(self._runs.get(analysis_id))

    def update_report(self, analysis_id: str, **fragments) -> None:
        """Persist intermediate report fragments only while the run is active."""
        with self._lock:
            run = self._runs.get(analysis_id)
            if run and run.status in {"queued", "running"}:
                for name, value in fragments.items():
                    setattr(run, name, deepcopy(value))
                run.updated_at = datetime.now(timezone.utc)

    def update_stage(
        self,
        analysis_id: str,
        *,
        status: str,
        stage: str,
        progress_percent: int,
        warnings: Optional[list[str]] = None,
    ) -> Optional[StoredCourtroomRun]:
        """Update run stage metadata."""
        with self._lock:
            run = self._runs.get(analysis_id)
            if run is None or run.status not in {"queued", "running"}:
                return None
            run.status = status
            run.stage = stage
            run.progress_percent = progress_percent
            run.updated_at = datetime.now(timezone.utc)
            if status in {"failed", "cancelled"}:
                run.completed_at = run.updated_at
            if warnings:
                run.warnings.extend(warnings)
            return run

    def append_trial_event(
        self, analysis_id: str, event: dict[str, Any]
    ) -> Optional[StoredCourtroomRun]:
        """Append a single trial event to the run log."""
        with self._lock:
            run = self._runs.get(analysis_id)
            if run is None or run.status not in {"queued", "running"}:
                return None
            run.trial_events.append(event)
            run.updated_at = datetime.now(timezone.utc)
            return run

    def append_trial_events(
        self, analysis_id: str, events: list[dict[str, Any]]
    ) -> Optional[StoredCourtroomRun]:
        """Append multiple trial events to the run log."""
        with self._lock:
            run = self._runs.get(analysis_id)
            if run is None or run.status not in {"queued", "running"}:
                return None
            run.trial_events.extend(events)
            run.updated_at = datetime.now(timezone.utc)
            return run

    def get_trial_events(self, analysis_id: str) -> list[dict[str, Any]]:
        """Return a copy of the persisted trial events."""
        with self._lock:
            run = self._runs.get(analysis_id)
            if run is None:
                return []
            return deepcopy(run.trial_events)

    def set_completed(
        self,
        analysis_id: str,
        role_analyses: list[dict[str, Any]],
        evaluation_breakdown: list[dict[str, Any]],
        synthesis: dict[str, Any],
        transparency_dashboard: dict[str, Any],
        rebuttal_changes: Optional[list[str]] = None,
        warnings: Optional[list[str]] = None,
        status: str = "completed",
    ) -> Optional[StoredCourtroomRun]:
        """Persist final report payload and mark run complete/degraded."""
        with self._lock:
            run = self._runs.get(analysis_id)
            if run is None or run.status not in {"queued", "running"}:
                return None
            now = datetime.now(timezone.utc)
            run.status = status
            run.stage = "completed"
            run.progress_percent = 100
            run.updated_at = now
            run.completed_at = now
            run.role_analyses = role_analyses
            run.evaluation_breakdown = evaluation_breakdown
            run.synthesis = synthesis
            run.transparency_dashboard = transparency_dashboard
            run.rebuttal_changes = rebuttal_changes or []
            if warnings:
                run.warnings.extend(warnings)
            if run.run_key and run.status == "completed":
                self._cache[run.run_key] = run.analysis_id
            return run

    def cancel(self, analysis_id: str) -> Optional[StoredCourtroomRun]:
        """Cancel a queued/running run."""
        with self._lock:
            run = self._runs.get(analysis_id)
            if run is None:
                return None
            if run.status in {"completed", "degraded", "failed", "cancelled"}:
                return run
            now = datetime.now(timezone.utc)
            run.status = "cancelled"
            run.stage = "cancelled"
            run.progress_percent = 100
            run.updated_at = now
            run.completed_at = now
            run.warnings.append("Analysis cancelled by user request.")
            return run
