"""Application service for Phase 4 simulated courtroom."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import time

from src.features.courtroom.cost_tracker import CourtroomCostTracker
from src.features.courtroom.evaluation_engine import CourtroomEvaluationEngine
from src.features.courtroom.orchestrator import CourtroomOrchestrator
from src.features.courtroom.rebuttal_engine import CourtroomRebuttalEngine
from src.features.courtroom.run_store import (
    InMemoryCourtroomRunStore,
    StoredCourtroomRun,
)
from src.features.courtroom.scoring import (
    average_weighted_score,
    consensus_and_disagreement,
    criteria_averages,
    evaluator_summary,
    score_matrix,
)
from src.features.courtroom.schemas import (
    CancelCourtroomAnalysisResponse,
    CourtroomAnalysisResponse,
    CourtroomAnalysisStatusResponse,
    CourtroomAnalyzeRequest,
    CourtroomEvaluationItem,
    CourtroomRoleAnalysis,
    CourtroomTransparencyDashboard,
    CreateCourtroomAnalysisResponse,
)
from src.features.courtroom.synthesis_engine import CourtroomSynthesisEngine


class CourtroomRunNotFoundError(Exception):
    """Raised when courtroom analysis id is not found."""


class CourtroomService:
    """Coordinates simulated courtroom analysis run lifecycle."""

    DISCLAIMER = (
        "NyayaAI simulated courtroom is a legal decision support workflow. "
        "It is not legal advice and does not replace judicial discretion or counsel."
    )

    def __init__(self):
        self.store = InMemoryCourtroomRunStore()
        self.orchestrator = CourtroomOrchestrator()
        self.evaluation_engine = CourtroomEvaluationEngine()
        self.rebuttal_engine = CourtroomRebuttalEngine()
        self.synthesis_engine = CourtroomSynthesisEngine()

    def create_analysis(
        self, payload: CourtroomAnalyzeRequest
    ) -> CreateCourtroomAnalysisResponse:
        """Create and execute a simulated courtroom analysis run."""
        start = time.perf_counter()

        include_rebuttal = bool(payload.include_rebuttal)
        if payload.mode == "quick" and include_rebuttal:
            include_rebuttal = False

        source_text, source_warnings = self._resolve_case_text(payload)
        run_key = self._compute_run_key(payload, source_text, include_rebuttal)

        cached = self.store.get_cached_completed(run_key)
        if cached is not None:
            return CreateCourtroomAnalysisResponse(
                analysis_id=cached.analysis_id,
                status=cached.status,
                mode=cached.mode,
                created_at=cached.created_at,
                eta_seconds=0,
                warnings=cached.warnings
                + [
                    "Cached courtroom analysis reused for identical input/mode configuration."
                ],
            )

        if payload.source_type == "case_id":
            input_ref = str(payload.case_id) if payload.case_id is not None else None
        else:
            input_ref = f"text:{len((source_text or '').strip())}"

        run = self.store.create_run(
            mode=payload.mode,
            include_rebuttal=include_rebuttal,
            input_source=payload.source_type,
            input_ref=input_ref,
            run_key=run_key,
        )

        warnings = list(source_warnings)
        tracker = CourtroomCostTracker()

        # Stage 1: retrieval + role analyses
        self.store.update_stage(
            run.analysis_id,
            status="running",
            stage="role_analysis",
            progress_percent=20,
        )
        role_analyses, role_warnings = self.orchestrator.run_initial_role_analyses(
            mode=payload.mode,
            case_text=source_text,
            top_k_legal=payload.top_k_legal,
            role_model_overrides=payload.role_model_overrides,
        )
        warnings.extend(role_warnings)
        for item in role_analyses:
            tracker.add_event(
                category="role_analysis",
                provider=item.provider or "fallback",
                model=item.model or "unknown",
                text=item.analysis_text,
            )

        # Stage 2: anonymous cross-evaluation
        self.store.update_stage(
            run.analysis_id,
            status="running",
            stage="cross_evaluation",
            progress_percent=50,
        )
        evaluation, eval_warnings = self.evaluation_engine.run_peer_evaluation(
            role_analyses,
            role_model_overrides=payload.role_model_overrides,
        )
        warnings.extend(eval_warnings)
        for ev in evaluation:
            tracker.add_scalar_event(
                category="peer_evaluation",
                provider="fallback",
                model="rubric-evaluator",
                tokens=max(80, int(len(ev.justification.split()) * 1.4)),
            )

        rebuttal_changes: list[str] = []
        final_role_analyses = role_analyses
        final_evaluation: list[CourtroomEvaluationItem] = evaluation

        # Stage 3: rebuttal + second evaluation (full mode)
        if include_rebuttal and payload.mode == "full":
            self.store.update_stage(
                run.analysis_id,
                status="running",
                stage="rebuttal",
                progress_percent=68,
            )
            revised, change_notes, rebuttal_warnings = (
                self.rebuttal_engine.run_rebuttal_round(
                    role_analyses=role_analyses,
                    evaluation_breakdown=evaluation,
                    mode=payload.mode,
                    enabled=True,
                    role_model_overrides=payload.role_model_overrides,
                )
            )
            final_role_analyses = revised
            rebuttal_changes = change_notes
            warnings.extend(rebuttal_warnings)

            for item in revised:
                tracker.add_event(
                    category="rebuttal",
                    provider=item.provider or "fallback",
                    model=item.model or "unknown",
                    text=item.analysis_text,
                )

            self.store.update_stage(
                run.analysis_id,
                status="running",
                stage="second_evaluation",
                progress_percent=80,
            )
            second_eval, second_eval_warnings = (
                self.evaluation_engine.run_peer_evaluation(
                    revised,
                    role_model_overrides=payload.role_model_overrides,
                )
            )
            final_evaluation = second_eval
            warnings.extend(second_eval_warnings)
            rebuttal_changes.extend(
                self._evaluation_delta_summary(evaluation, second_eval)
            )

        # Stage 4: judge synthesis
        self.store.update_stage(
            run.analysis_id,
            status="running",
            stage="synthesis",
            progress_percent=92,
        )
        synthesis, synthesis_warnings = self.synthesis_engine.synthesize(
            mode=payload.mode,
            role_analyses=final_role_analyses,
            evaluation_breakdown=final_evaluation,
            rebuttal_changes=rebuttal_changes,
            role_model_overrides=payload.role_model_overrides,
        )
        warnings.extend(synthesis_warnings)
        tracker.add_event(
            category="synthesis",
            provider="fallback",
            model="judge-synthesizer",
            text=synthesis.executive_summary + "\n" + synthesis.recommended_outcome,
        )

        total_runtime_ms = int((time.perf_counter() - start) * 1000)
        transparency = self._build_transparency(
            evaluation_items=final_evaluation,
            tracker=tracker,
            total_runtime_ms=total_runtime_ms,
        )

        if (
            payload.max_cost_usd is not None
            and transparency.estimated_cost_usd > payload.max_cost_usd
        ):
            warnings.append(
                "Estimated run cost exceeded max_cost_usd guardrail; review role/model routing for budget control."
            )

        any_degraded = any(item.degraded for item in final_role_analyses)
        if any_degraded or any("fallback" in w.lower() for w in warnings):
            final_status = "degraded"
        else:
            final_status = "completed"

        self.store.set_completed(
            run.analysis_id,
            role_analyses=[item.model_dump() for item in final_role_analyses],
            evaluation_breakdown=[item.model_dump() for item in final_evaluation],
            synthesis=synthesis.model_dump(),
            transparency_dashboard=transparency.model_dump(),
            rebuttal_changes=rebuttal_changes,
            warnings=warnings,
            status=final_status,
        )

        completed = self._require_run(run.analysis_id)
        return CreateCourtroomAnalysisResponse(
            analysis_id=completed.analysis_id,
            status=completed.status,
            mode=completed.mode,
            created_at=completed.created_at,
            eta_seconds=0,
            warnings=completed.warnings,
        )

    def get_analysis(self, analysis_id: str) -> CourtroomAnalysisResponse:
        """Return full courtroom report by analysis id."""
        run = self._require_run(analysis_id)
        return CourtroomAnalysisResponse(
            analysis_id=run.analysis_id,
            status=run.status,
            mode=run.mode,
            created_at=run.created_at,
            completed_at=run.completed_at,
            role_analyses=[
                CourtroomRoleAnalysis.model_validate(item) for item in run.role_analyses
            ],
            evaluation_breakdown=[
                CourtroomEvaluationItem.model_validate(item)
                for item in run.evaluation_breakdown
            ],
            rebuttal_enabled=run.include_rebuttal,
            rebuttal_changes=run.rebuttal_changes,
            synthesis=run.synthesis,
            transparency_dashboard=run.transparency_dashboard,
            disclaimer=self.DISCLAIMER,
            warnings=run.warnings,
        )

    def get_status(self, analysis_id: str) -> CourtroomAnalysisStatusResponse:
        """Return lightweight status payload for a run."""
        run = self._require_run(analysis_id)
        return CourtroomAnalysisStatusResponse(
            analysis_id=run.analysis_id,
            status=run.status,
            stage=run.stage,
            progress_percent=run.progress_percent,
            updated_at=run.updated_at,
            warnings=run.warnings,
        )

    def cancel_analysis(self, analysis_id: str) -> CancelCourtroomAnalysisResponse:
        """Cancel an in-flight run when possible."""
        existing = self._require_run(analysis_id)
        was_terminal = existing.status in {
            "completed",
            "degraded",
            "failed",
            "cancelled",
        }
        updated = self.store.cancel(analysis_id)
        if updated is None:
            raise CourtroomRunNotFoundError("Courtroom analysis not found")
        return CancelCourtroomAnalysisResponse(
            analysis_id=analysis_id,
            cancelled=not was_terminal and updated.status == "cancelled",
            status=updated.status,
        )

    def _require_run(self, analysis_id: str) -> StoredCourtroomRun:
        run = self.store.get_run(analysis_id)
        if run is None:
            raise CourtroomRunNotFoundError("Courtroom analysis not found")
        return run

    def _resolve_case_text(
        self, payload: CourtroomAnalyzeRequest
    ) -> tuple[str, list[str]]:
        """Resolve case input into analysis text with warnings."""
        warnings: list[str] = []

        if payload.source_type == "text":
            text = (payload.case_text or "").strip()
            if not text:
                warnings.append(
                    "No case_text supplied; using placeholder facts for scaffolding output."
                )
                text = (
                    "Placeholder case facts: allegations, defense submissions, and procedural "
                    "history were not provided by the requester."
                )
            return text, warnings

        # source_type == case_id
        if payload.case_id is None:
            warnings.append(
                "source_type=case_id requested without case_id; using placeholder facts."
            )
            return (
                "Placeholder case facts for missing case_id. Detailed record lookup will be "
                "integrated in subsequent iterations.",
                warnings,
            )

        warnings.append(
            "Case-id source lookup is currently scaffolded; full DB fetch integration is pending next iteration."
        )
        return (
            f"Case record reference: case_id={payload.case_id}. "
            "Detailed factual and evidentiary text extraction from DB will be added in a follow-up iteration.",
            warnings,
        )

    def _compute_run_key(
        self,
        payload: CourtroomAnalyzeRequest,
        source_text: str,
        include_rebuttal: bool,
    ) -> str:
        """Build deterministic cache key for identical runs."""
        key_payload = {
            "mode": payload.mode,
            "include_rebuttal": include_rebuttal,
            "source_type": payload.source_type,
            "case_id": payload.case_id,
            "top_k_legal": payload.top_k_legal,
            "top_k_cases": payload.top_k_cases,
            "role_model_overrides": payload.role_model_overrides,
            "max_cost_usd": payload.max_cost_usd,
            "source_hash": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        }
        blob = json.dumps(key_payload, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _build_transparency(
        self,
        *,
        evaluation_items: list[CourtroomEvaluationItem],
        tracker: CourtroomCostTracker,
        total_runtime_ms: int,
    ) -> CourtroomTransparencyDashboard:
        """Build transparency dashboard payload from scoring and cost estimations."""
        consensus, disagreement = consensus_and_disagreement(evaluation_items)
        matrix = score_matrix(evaluation_items)
        crit_avg = criteria_averages(evaluation_items)
        evaluator_stats = evaluator_summary(evaluation_items)

        # Adjust cost by evaluation density to avoid underestimating heavy runs.
        eval_complexity = max(1.0, len(evaluation_items) / 6.0)
        estimated_cost = round(tracker.total_cost() * eval_complexity, 4)

        return CourtroomTransparencyDashboard(
            consensus_meter=consensus,
            disagreement_index=disagreement,
            estimated_cost_usd=estimated_cost,
            total_runtime_ms=total_runtime_ms,
            estimated_token_usage=tracker.total_tokens(),
            score_matrix=matrix,
            criteria_averages=crit_avg,
            evaluator_summary=evaluator_stats,
        )

    def _evaluation_delta_summary(
        self,
        first_pass: list[CourtroomEvaluationItem],
        second_pass: list[CourtroomEvaluationItem],
    ) -> list[str]:
        """Build human-readable delta notes between first and second scoring passes."""
        first_avg = average_weighted_score(first_pass)
        second_avg = average_weighted_score(second_pass)
        delta = round(second_avg - first_avg, 2)
        return [f"Second-pass average weighted score: {second_avg} (delta {delta:+})."]
