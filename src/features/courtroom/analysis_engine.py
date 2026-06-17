"""Role analysis engine for courtroom simulation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any

from loguru import logger

from src.config.settings import settings
from src.features.courtroom.model_registry import CourtroomModelRegistry, ModelRoute
from src.features.courtroom.roles import (
    build_role_system_prompt,
    build_role_user_prompt,
)
from src.features.courtroom.schemas import CourtroomRoleAnalysis
from src.utils.llm_client import LLMClient


@dataclass
class RoleAnalysisResult:
    """Result container for role analysis call."""

    analysis: CourtroomRoleAnalysis
    warnings: list[str]


class CourtroomAnalysisEngine:
    """Executes role-level legal analyses with provider/model fallbacks."""

    def __init__(self) -> None:
        self.registry = CourtroomModelRegistry()
        self.live_enabled = settings.courtroom_enable_live_llm and not bool(
            os.getenv("PYTEST_CURRENT_TEST")
        )

    def run_role(
        self,
        role_name: str,
        case_text: str,
        mode: str,
        evidence_blocks: list[dict[str, str]] | None = None,
        role_model_overrides: dict[str, list[dict[str, str]]] | None = None,
    ) -> RoleAnalysisResult:
        """Run one role analysis with fallback chain."""
        warnings: list[str] = []
        chain = self._chain_for_role(role_name, role_model_overrides)
        if not chain:
            warnings.append(
                f"No configured available model route for role '{role_name}', using deterministic fallback."
            )
            return RoleAnalysisResult(
                analysis=self._fallback_analysis(role_name, mode, degraded=True),
                warnings=warnings,
            )

        if not self.live_enabled:
            warnings.append(
                "Live LLM disabled for current runtime; using deterministic fallback."
            )
            return RoleAnalysisResult(
                analysis=self._fallback_analysis(role_name, mode, degraded=True),
                warnings=warnings,
            )

        for route in chain:
            try:
                analysis = self._run_with_route(
                    route=route,
                    role_name=role_name,
                    case_text=case_text,
                    mode=mode,
                    evidence_blocks=evidence_blocks or [],
                )
                return RoleAnalysisResult(analysis=analysis, warnings=warnings)
            except Exception as exc:
                warnings.append(
                    f"Route {route.provider}:{route.model} failed for {role_name}: {str(exc)}"
                )
                logger.warning(
                    "Courtroom role route failed",
                    role=role_name,
                    provider=route.provider,
                    model=route.model,
                    error=str(exc),
                )

        warnings.append(
            f"All model routes failed for role '{role_name}', using fallback."
        )
        return RoleAnalysisResult(
            analysis=self._fallback_analysis(role_name, mode, degraded=True),
            warnings=warnings,
        )

    def _chain_for_role(
        self,
        role_name: str,
        role_model_overrides: dict[str, list[dict[str, str]]] | None,
    ) -> list[ModelRoute]:
        if role_model_overrides:
            override_registry = CourtroomModelRegistry(
                role_override_map=role_model_overrides
            )
            return override_registry.get_chain(role_name)
        return self.registry.get_chain(role_name)

    def _run_with_route(
        self,
        route: ModelRoute,
        role_name: str,
        case_text: str,
        mode: str,
        evidence_blocks: list[dict[str, str]],
    ) -> CourtroomRoleAnalysis:
        client = LLMClient(provider=route.provider, model=route.model)
        system_prompt = build_role_system_prompt(role_name)  # type: ignore[arg-type]
        prompt = build_role_user_prompt(
            role_name, case_text, mode, evidence_blocks=evidence_blocks
        )  # type: ignore[arg-type]

        raw = client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.15,
            max_tokens=650,
        )
        parsed = self._parse_role_json(raw)

        analysis_text = str(parsed.get("analysis_text") or "").strip()
        if not analysis_text:
            raise ValueError("Missing analysis_text in role output")

        citations_raw = parsed.get("citations")
        citations: list[str] = []
        if isinstance(citations_raw, list):
            citations = [str(c).strip() for c in citations_raw if str(c).strip()][:8]

        confidence_raw = parsed.get("confidence", 0.55)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.55
        confidence = max(0.0, min(1.0, confidence))

        return CourtroomRoleAnalysis(
            role_name=role_name,
            analysis_text=analysis_text,
            citations=citations,
            confidence=confidence,
            provider=route.provider,
            model=route.model,
            degraded=False,
        )

    def _parse_role_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Recover first JSON object if wrapper text leaked in.
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("Unable to parse role analysis JSON")

    def _fallback_analysis(
        self,
        role_name: str,
        mode: str,
        degraded: bool,
    ) -> CourtroomRoleAnalysis:
        return CourtroomRoleAnalysis(
            role_name=role_name,
            analysis_text=(
                f"{role_name} fallback analysis generated because live model routes were unavailable. "
                f"Mode={mode}. This output preserves response structure for downstream scoring/synthesis."
            ),
            citations=[
                "Section reference pending retrieval",
                "Article reference pending retrieval",
            ],
            confidence=0.45,
            provider="fallback",
            model="deterministic-template",
            degraded=degraded,
        )

    def build_fallback_analysis(
        self,
        role_name: str,
        mode: str,
        degraded: bool = True,
    ) -> CourtroomRoleAnalysis:
        """Public helper to generate deterministic fallback role output."""
        return self._fallback_analysis(
            role_name=role_name, mode=mode, degraded=degraded
        )
