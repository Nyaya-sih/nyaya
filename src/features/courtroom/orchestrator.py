"""Parallel orchestration for courtroom role analyses."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config.settings import settings
from src.features.courtroom.analysis_engine import (
    CourtroomAnalysisEngine,
    RoleAnalysisResult,
)
from src.features.courtroom.retrieval_adapter import CourtroomRetrievalAdapter
from src.features.courtroom.roles import FULL_MODE_ROLES, QUICK_MODE_ROLES
from src.features.courtroom.schemas import CourtroomRoleAnalysis


class CourtroomOrchestrator:
    """Coordinates parallel execution of role analyses."""

    def __init__(self) -> None:
        self.analysis_engine = CourtroomAnalysisEngine()
        self.retrieval_adapter = CourtroomRetrievalAdapter()

    def run_initial_role_analyses(
        self,
        *,
        mode: str,
        case_text: str,
        top_k_legal: int,
        role_model_overrides: dict[str, list[dict[str, str]]] | None = None,
    ) -> tuple[list[CourtroomRoleAnalysis], list[str]]:
        """Run role analyses in parallel for selected mode."""
        roles = QUICK_MODE_ROLES if mode == "quick" else FULL_MODE_ROLES

        max_workers = min(settings.courtroom_max_parallel_roles, len(roles))
        outputs: list[CourtroomRoleAnalysis] = []
        warnings: list[str] = []

        role_evidence: dict[str, list[dict[str, str]]] = {}
        for role in roles:
            blocks, retrieval_warnings = self.retrieval_adapter.retrieve_for_role(
                role_name=role,
                case_text=case_text,
                top_k_legal=top_k_legal,
            )
            role_evidence[role] = blocks
            warnings.extend(retrieval_warnings)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    self.analysis_engine.run_role,
                    role_name=role,
                    case_text=case_text,
                    mode=mode,
                    evidence_blocks=role_evidence.get(role, []),
                    role_model_overrides=role_model_overrides,
                ): role
                for role in roles
            }

            for future in as_completed(futures):
                role = futures[future]
                try:
                    result: RoleAnalysisResult = future.result()
                    outputs.append(result.analysis)
                    warnings.extend(result.warnings)
                except Exception as exc:
                    warnings.append(
                        f"Role execution failed for {role}: {str(exc)}; deterministic fallback injected."
                    )
                    outputs.append(
                        self.analysis_engine.build_fallback_analysis(
                            role_name=role, mode=mode, degraded=True
                        )
                    )

        role_order = {name: idx for idx, name in enumerate(roles)}
        outputs.sort(key=lambda item: role_order.get(item.role_name, 999))
        return outputs, warnings
