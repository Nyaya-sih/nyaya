"""Judge synthesis engine for courtroom deliberation reports."""

from __future__ import annotations

import json
import os
import re

from loguru import logger

from src.features.courtroom.model_registry import CourtroomModelRegistry, ModelRoute
from src.features.courtroom.schemas import (
    CourtroomEvaluationItem,
    CourtroomRoleAnalysis,
    CourtroomSynthesis,
)
from src.utils.llm_client import LLMClient


class CourtroomSynthesisEngine:
    """Generate presiding-judge synthesis from role analyses and rubric outcomes."""

    def __init__(self) -> None:
        self.registry = CourtroomModelRegistry()
        self.live_enabled = not bool(os.getenv("PYTEST_CURRENT_TEST"))

    def synthesize(
        self,
        *,
        mode: str,
        role_analyses: list[CourtroomRoleAnalysis],
        evaluation_breakdown: list[CourtroomEvaluationItem],
        rebuttal_changes: list[str],
        role_model_overrides: dict[str, list[dict[str, str]]] | None = None,
    ) -> tuple[CourtroomSynthesis, list[str]]:
        """Return synthesis object and warnings."""
        warnings: list[str] = []

        if not self.live_enabled:
            warnings.append(
                "Live judge synthesis disabled in test runtime; fallback used."
            )
            return self._fallback_synthesis(
                mode, role_analyses, evaluation_breakdown
            ), warnings

        chain = self._judge_chain(role_model_overrides)
        if not chain:
            warnings.append(
                "No model route configured for Presiding Judge; fallback synthesis used."
            )
            return self._fallback_synthesis(
                mode, role_analyses, evaluation_breakdown
            ), warnings

        for route in chain:
            try:
                return (
                    self._synthesize_with_route(
                        route=route,
                        mode=mode,
                        role_analyses=role_analyses,
                        evaluation_breakdown=evaluation_breakdown,
                        rebuttal_changes=rebuttal_changes,
                    ),
                    warnings,
                )
            except Exception as exc:
                warnings.append(
                    f"Judge synthesis route {route.provider}:{route.model} failed: {str(exc)}"
                )
                logger.warning(
                    "Judge synthesis route failed",
                    provider=route.provider,
                    model=route.model,
                    error=str(exc),
                )

        warnings.append("All judge synthesis routes failed; fallback synthesis used.")
        return self._fallback_synthesis(
            mode, role_analyses, evaluation_breakdown
        ), warnings

    def _judge_chain(
        self,
        role_model_overrides: dict[str, list[dict[str, str]]] | None,
    ) -> list[ModelRoute]:
        if role_model_overrides:
            override_registry = CourtroomModelRegistry(
                role_override_map=role_model_overrides
            )
            return override_registry.get_chain("Presiding Judge")
        return self.registry.get_chain("Presiding Judge")

    def _synthesize_with_route(
        self,
        *,
        route: ModelRoute,
        mode: str,
        role_analyses: list[CourtroomRoleAnalysis],
        evaluation_breakdown: list[CourtroomEvaluationItem],
        rebuttal_changes: list[str],
    ) -> CourtroomSynthesis:
        client = LLMClient(provider=route.provider, model=route.model)

        role_text = []
        for item in role_analyses:
            role_text.append(
                f"Role={item.role_name} confidence={item.confidence:.2f} degraded={item.degraded}\n"
                f"{item.analysis_text[:900]}"
            )
        eval_text = []
        for ev in evaluation_breakdown[:20]:
            eval_text.append(
                f"{ev.evaluator_role} -> {ev.target_role}: weighted={ev.weighted_score}\n{ev.justification[:220]}"
            )

        rebuttal_text = (
            "\n".join(rebuttal_changes[:8])
            if rebuttal_changes
            else "No rebuttal changes."
        )

        system_prompt = (
            "You are the Presiding Judge synthesizer in a simulated legal deliberation. "
            "Synthesize only from provided role analyses and evaluation notes. "
            "Be balanced, explicit about unresolved issues, and avoid deterministic overclaiming. "
            "Return JSON only."
        )
        prompt = (
            f"Mode: {mode}\n\n"
            f"Role analyses:\n{'\n\n'.join(role_text)}\n\n"
            f"Evaluation highlights:\n{'\n'.join(eval_text)}\n\n"
            f"Rebuttal summary:\n{rebuttal_text}\n\n"
            "Return JSON schema:\n"
            "{\n"
            '  "executive_summary": "<2-3 paragraph summary>",\n'
            '  "recommended_outcome": "<structured recommendation with caveat>",\n'
            '  "confidence": <0-1>,\n'
            '  "consensus_points": ["..."],\n'
            '  "disagreement_points": ["..."],\n'
            '  "unresolved_issues": ["..."],\n'
            '  "legal_principles_applied": ["..."]\n'
            "}"
        )
        raw = client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=700,
        )
        parsed = self._parse_json(raw)

        return CourtroomSynthesis(
            executive_summary=str(parsed.get("executive_summary") or "").strip()
            or "Judge synthesis unavailable.",
            recommended_outcome=str(parsed.get("recommended_outcome") or "").strip()
            or "No recommendation.",
            confidence=self._bounded_confidence(parsed.get("confidence", 0.55)),
            consensus_points=self._as_list(parsed.get("consensus_points")),
            disagreement_points=self._as_list(parsed.get("disagreement_points")),
            unresolved_issues=self._as_list(parsed.get("unresolved_issues")),
            legal_principles_applied=self._as_list(
                parsed.get("legal_principles_applied")
            ),
        )

    def _fallback_synthesis(
        self,
        mode: str,
        role_analyses: list[CourtroomRoleAnalysis],
        evaluation_breakdown: list[CourtroomEvaluationItem],
    ) -> CourtroomSynthesis:
        degraded_count = sum(1 for r in role_analyses if r.degraded)
        avg_conf = (
            sum(r.confidence for r in role_analyses) / len(role_analyses)
            if role_analyses
            else 0.45
        )
        max_eval = max((e.weighted_score for e in evaluation_breakdown), default=0.0)

        return CourtroomSynthesis(
            executive_summary=(
                "The simulated courtroom indicates contestable merits on both sides. "
                "Outcome sensitivity remains high to evidentiary reliability and procedural compliance."
            ),
            recommended_outcome=(
                "Proceed with caution: no deterministic recommendation is issued in fallback mode; "
                "seek deeper role-specific evidence development."
            ),
            confidence=round(
                max(0.35, min(0.78, (avg_conf * 0.7) + (max_eval / 300))), 3
            ),
            consensus_points=[
                "Evidentiary credibility is central to adjudication.",
                "Procedural safeguards materially affect final disposition.",
            ],
            disagreement_points=[
                "Relative strength of prosecutorial vs defensive legal framing.",
                "Degree of constitutional scrutiny required for relief.",
            ],
            unresolved_issues=[
                "Further jurisprudential alignment required for final recommendation.",
                f"Degraded role outputs count: {degraded_count}."
                if degraded_count
                else "",
            ],
            legal_principles_applied=[
                "burden of proof",
                "procedural fairness",
                "reasoned judicial discretion",
            ],
        )

    def _parse_json(self, raw: str) -> dict:
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

        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("Unable to parse synthesis JSON")

    @staticmethod
    def _as_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()][:10]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _bounded_confidence(value: object) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.55
        return max(0.0, min(1.0, score))
