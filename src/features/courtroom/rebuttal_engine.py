"""Rebuttal round engine for full courtroom mode."""

from __future__ import annotations

import json
import os
import re

from loguru import logger

from src.features.courtroom.model_registry import CourtroomModelRegistry, ModelRoute
from src.features.courtroom.schemas import (
    CourtroomEvaluationItem,
    CourtroomRoleAnalysis,
)
from src.utils.llm_client import LLMClient


class CourtroomRebuttalEngine:
    """Generate revised role analyses based on anonymized critiques."""

    def __init__(self) -> None:
        self.registry = CourtroomModelRegistry()
        self.live_enabled = not bool(os.getenv("PYTEST_CURRENT_TEST"))

    def run_rebuttal_round(
        self,
        role_analyses: list[CourtroomRoleAnalysis],
        evaluation_breakdown: list[CourtroomEvaluationItem],
        mode: str,
        enabled: bool,
        role_model_overrides: dict[str, list[dict[str, str]]] | None = None,
    ) -> tuple[list[CourtroomRoleAnalysis], list[str], list[str]]:
        """Return revised role analyses, change notes, and warnings."""
        if not enabled or mode != "full":
            return role_analyses, [], []

        revised: list[CourtroomRoleAnalysis] = []
        changes: list[str] = []
        warnings: list[str] = []

        for role_analysis in role_analyses:
            critiques = [
                item
                for item in evaluation_breakdown
                if item.target_role == role_analysis.role_name
            ]
            updated, update_notes, local_warnings = self._revise_role(
                role_analysis=role_analysis,
                critiques=critiques,
                role_model_overrides=role_model_overrides,
            )
            revised.append(updated)
            changes.append(update_notes)
            warnings.extend(local_warnings)

        return revised, changes, warnings

    def _revise_role(
        self,
        *,
        role_analysis: CourtroomRoleAnalysis,
        critiques: list[CourtroomEvaluationItem],
        role_model_overrides: dict[str, list[dict[str, str]]] | None,
    ) -> tuple[CourtroomRoleAnalysis, str, list[str]]:
        warnings: list[str] = []

        if not critiques:
            return (
                role_analysis,
                f"{role_analysis.role_name}: no critiques received.",
                warnings,
            )

        chain = self._chain_for_role(role_analysis.role_name, role_model_overrides)
        if not self.live_enabled or not chain:
            notes = f"{role_analysis.role_name}: rebuttal fallback applied; critiques acknowledged without live model revision."
            updated = role_analysis.model_copy(
                update={
                    "analysis_text": role_analysis.analysis_text
                    + "\n\nRebuttal note: Critiques acknowledged; additional clarification required in next iteration.",
                    "degraded": True,
                }
            )
            if not chain:
                warnings.append(
                    f"No rebuttal model route for {role_analysis.role_name}; fallback used."
                )
            elif not self.live_enabled:
                warnings.append(
                    "Live rebuttal disabled in test runtime; fallback used."
                )
            return updated, notes, warnings

        critique_lines = []
        for item in critiques:
            critique_lines.append(
                f"From {item.evaluator_role}: weighted={item.weighted_score}\n{item.justification}"
            )
        critique_text = "\n\n".join(critique_lines)

        for route in chain:
            try:
                client = LLMClient(provider=route.provider, model=route.model)
                system_prompt = (
                    "You are revising a legal role analysis after peer critique in a simulated courtroom. "
                    "Preserve role stance but improve legal precision and response to critiques. "
                    "Return JSON only."
                )
                prompt = (
                    f"Role: {role_analysis.role_name}\n\n"
                    f"Original analysis:\n{role_analysis.analysis_text[:2500]}\n\n"
                    f"Critiques:\n{critique_text[:2500]}\n\n"
                    "Return JSON schema:\n"
                    "{\n"
                    '  "revised_analysis_text": "<revised legal analysis>",\n'
                    '  "revision_notes": "<what was improved>",\n'
                    '  "citations": ["Section ...", "Article ..."],\n'
                    '  "confidence": <0-1>\n'
                    "}"
                )
                raw = client.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.2,
                    max_tokens=520,
                )
                parsed = self._parse_json(raw)

                revised_text = str(parsed.get("revised_analysis_text") or "").strip()
                if not revised_text:
                    raise ValueError("revised_analysis_text missing")

                revision_notes = str(
                    parsed.get("revision_notes") or "No revision notes."
                )
                citations_raw = parsed.get("citations")
                citations = (
                    [str(c).strip() for c in citations_raw if str(c).strip()][:10]
                    if isinstance(citations_raw, list)
                    else role_analysis.citations
                )
                conf_raw = parsed.get("confidence", role_analysis.confidence)
                try:
                    confidence = float(conf_raw)
                except (TypeError, ValueError):
                    confidence = role_analysis.confidence
                confidence = max(0.0, min(1.0, confidence))

                updated = role_analysis.model_copy(
                    update={
                        "analysis_text": revised_text,
                        "citations": citations,
                        "confidence": confidence,
                        "provider": route.provider,
                        "model": route.model,
                        "degraded": False,
                    }
                )
                notes = f"{role_analysis.role_name}: {revision_notes}"
                return updated, notes, warnings
            except Exception as exc:
                warnings.append(
                    f"Rebuttal route {route.provider}:{route.model} failed for {role_analysis.role_name}: {str(exc)}"
                )
                logger.warning(
                    "Rebuttal route failed",
                    role=role_analysis.role_name,
                    provider=route.provider,
                    model=route.model,
                    error=str(exc),
                )

        updated = role_analysis.model_copy(
            update={
                "analysis_text": role_analysis.analysis_text
                + "\n\nRebuttal note: Critiques considered; live revision route failed.",
                "degraded": True,
            }
        )
        notes = f"{role_analysis.role_name}: live rebuttal unavailable; fallback text appended."
        return updated, notes, warnings

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
        raise ValueError("Unable to parse rebuttal JSON")
