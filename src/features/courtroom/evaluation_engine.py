"""Anonymous cross-evaluation engine for courtroom analyses."""

from __future__ import annotations

import json
import os
import re

from loguru import logger

from src.config.settings import settings

from src.features.courtroom.anonymizer import AnalysisAnonymizer, AnonymousAnalysis
from src.features.courtroom.model_registry import CourtroomModelRegistry, ModelRoute
from src.features.courtroom.scoring import weighted_score
from src.features.courtroom.schemas import (
    CourtroomCriteriaScores,
    CourtroomEvaluationItem,
    CourtroomRoleAnalysis,
)
from src.utils.llm_client import LLMClient


class CourtroomEvaluationEngine:
    """Run rubric scoring where each role evaluates other roles anonymously."""

    def __init__(self) -> None:
        self.registry = CourtroomModelRegistry()
        self.anonymizer = AnalysisAnonymizer()
        self.live_enabled = not bool(os.getenv("PYTEST_CURRENT_TEST"))

    def run_peer_evaluation(
        self,
        role_analyses: list[CourtroomRoleAnalysis],
        role_model_overrides: dict[str, list[dict[str, str]]] | None = None,
        *, is_cancelled=lambda: False,
    ) -> tuple[list[CourtroomEvaluationItem], list[str]]:
        """Run anonymous peer evaluation matrix with fallback behavior."""
        warnings: list[str] = []
        items: list[CourtroomEvaluationItem] = []

        anon_items, _, _ = self.anonymizer.anonymize(role_analyses)

        for evaluator in role_analyses:
            for target in anon_items:
                if is_cancelled():
                    return items, warnings
                if evaluator.role_name == target.role_name:
                    continue
                eval_item, local_warnings = self._evaluate_pair(
                    evaluator_role=evaluator.role_name,
                    target=target,
                    corpus=anon_items,
                    role_model_overrides=role_model_overrides,
                )
                warnings.extend(local_warnings)
                items.append(eval_item)

        return items, warnings

    def _evaluate_pair(
        self,
        *,
        evaluator_role: str,
        target: AnonymousAnalysis,
        corpus: list[AnonymousAnalysis],
        role_model_overrides: dict[str, list[dict[str, str]]] | None,
    ) -> tuple[CourtroomEvaluationItem, list[str]]:
        warnings: list[str] = []

        if not self.live_enabled or not settings.courtroom_enable_live_llm:
            warnings.append(
                "Live peer-evaluation disabled in test runtime; deterministic fallback used."
            )
            return self._fallback_eval(
                evaluator_role=evaluator_role, target=target
            ), warnings

        chain = self._chain_for_role(evaluator_role, role_model_overrides)
        if not chain:
            warnings.append(
                f"No model route available for evaluator role '{evaluator_role}'; fallback scoring used."
            )
            return self._fallback_eval(
                evaluator_role=evaluator_role, target=target
            ), warnings

        for route in chain:
            try:
                return self._score_with_route(
                    evaluator_role=evaluator_role,
                    target=target,
                    corpus=corpus,
                    route=route,
                ), warnings
            except Exception as exc:
                warnings.append(
                    f"Peer-evaluation route {route.provider}:{route.model} failed for {evaluator_role}: {str(exc)}"
                )
                logger.warning(
                    "Courtroom evaluator route failed",
                    evaluator=evaluator_role,
                    provider=route.provider,
                    model=route.model,
                    error=str(exc),
                )

        warnings.append(
            f"All peer-evaluation routes failed for evaluator '{evaluator_role}'; fallback scoring used."
        )
        return self._fallback_eval(
            evaluator_role=evaluator_role, target=target
        ), warnings

    def _chain_for_role(
        self,
        evaluator_role: str,
        role_model_overrides: dict[str, list[dict[str, str]]] | None,
    ) -> list[ModelRoute]:
        if role_model_overrides:
            override_registry = CourtroomModelRegistry(
                role_override_map=role_model_overrides
            )
            return override_registry.get_chain(evaluator_role)
        return self.registry.get_chain(evaluator_role)

    def _score_with_route(
        self,
        *,
        evaluator_role: str,
        target: AnonymousAnalysis,
        corpus: list[AnonymousAnalysis],
        route: ModelRoute,
    ) -> CourtroomEvaluationItem:
        client = LLMClient(provider=route.provider, model=route.model)

        peer_samples = []
        for item in corpus:
            if item.anonymous_id == target.anonymous_id:
                continue
            peer_samples.append(f"{item.anonymous_id}: {item.analysis_text[:220]}")
        peer_text = "\n".join(peer_samples[:3])

        system_prompt = (
            "You are a legal peer-review evaluator in a simulated courtroom. "
            "You are assigned an evaluator role and must score an anonymous analysis strictly by rubric. "
            "Return JSON only with numeric scores and concise justification."
        )
        prompt = (
            f"Evaluator role: {evaluator_role}\n"
            f"Target anonymous analysis: {target.anonymous_id}\n\n"
            f"Target text:\n{target.analysis_text[:1800]}\n\n"
            f"Other anonymous samples (for calibration, do not identify):\n{peer_text}\n\n"
            "Rubric weights: Legal Accuracy 25, Constitutional Alignment 20, Logical Coherence 20, "
            "Precedent Usage 15, Fairness & Balance 10, Practical Applicability 10.\n"
            "Return JSON schema:\n"
            "{\n"
            '  "legal_accuracy": <1-100>,\n'
            '  "constitutional_alignment": <1-100>,\n'
            '  "logical_coherence": <1-100>,\n'
            '  "precedent_usage": <1-100>,\n'
            '  "fairness_balance": <1-100>,\n'
            '  "practical_applicability": <1-100>,\n'
            '  "justification": "<2-4 sentence evaluation>"\n'
            "}"
        )

        raw = client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=350,
        )
        parsed = self._parse_json(raw)

        criteria = CourtroomCriteriaScores(
            legal_accuracy=self._bounded_score(parsed.get("legal_accuracy")),
            constitutional_alignment=self._bounded_score(
                parsed.get("constitutional_alignment")
            ),
            logical_coherence=self._bounded_score(parsed.get("logical_coherence")),
            precedent_usage=self._bounded_score(parsed.get("precedent_usage")),
            fairness_balance=self._bounded_score(parsed.get("fairness_balance")),
            practical_applicability=self._bounded_score(
                parsed.get("practical_applicability")
            ),
        )
        justification = str(
            parsed.get("justification") or "No evaluator justification supplied."
        )

        return CourtroomEvaluationItem(
            evaluator_role=evaluator_role,
            target_role=target.role_name,
            criteria_scores=criteria,
            weighted_score=weighted_score(criteria),
            justification=justification,
        )

    def _fallback_eval(
        self,
        *,
        evaluator_role: str,
        target: AnonymousAnalysis,
    ) -> CourtroomEvaluationItem:
        base = 65.0 + (target.confidence * 20.0)
        criteria = CourtroomCriteriaScores(
            legal_accuracy=min(95.0, base + 2),
            constitutional_alignment=min(95.0, base),
            logical_coherence=min(95.0, base + 1),
            precedent_usage=min(95.0, base - 1),
            fairness_balance=min(95.0, base),
            practical_applicability=min(95.0, base + 1),
        )
        return CourtroomEvaluationItem(
            evaluator_role=evaluator_role,
            target_role=target.role_name,
            criteria_scores=criteria,
            weighted_score=weighted_score(criteria),
            justification=(
                f"Deterministic fallback evaluation by {evaluator_role} for {target.anonymous_id} "
                "due to unavailable live evaluator route."
            ),
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
        raise ValueError("Unable to parse evaluator JSON")

    @staticmethod
    def _bounded_score(value: object) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 60.0
        return max(1.0, min(100.0, score))
