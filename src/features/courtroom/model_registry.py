"""Extensible model routing registry for courtroom roles."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from loguru import logger

from src.config.settings import settings


@dataclass
class ModelRoute:
    """Single provider/model route candidate."""

    provider: str
    model: str


class CourtroomModelRegistry:
    """Maps courtroom roles to ordered provider/model fallback chains."""

    DEFAULT_ROLE_CHAINS: dict[str, list[dict[str, str]]] = {
        "Prosecution Counsel": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            {"provider": "google", "model": "gemini-flash-latest"},
        ],
        "Defense Counsel": [
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "google", "model": "gemini-flash-latest"},
        ],
        "Constitutional Expert": [
            {"provider": "google", "model": "gemini-flash-latest"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        ],
        "Legal Analyst": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "google", "model": "gemini-flash-latest"},
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        ],
        "Presiding Judge": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "google", "model": "gemini-flash-latest"},
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        ],
    }

    def __init__(
        self, role_override_map: dict[str, list[dict[str, str]]] | None = None
    ) -> None:
        self.available_providers = set(settings.get_available_models())
        self._role_map = self._load_role_map(role_override_map)

    def _load_role_map(
        self, role_override_map: dict[str, list[dict[str, str]]] | None = None
    ) -> dict[str, list[ModelRoute]]:
        raw_map = self.DEFAULT_ROLE_CHAINS
        if settings.courtroom_role_model_map.strip():
            try:
                parsed = json.loads(settings.courtroom_role_model_map)
                if isinstance(parsed, dict):
                    raw_map = parsed
                else:
                    logger.warning(
                        "COURTROOM_ROLE_MODEL_MAP ignored; expected object mapping"
                    )
            except json.JSONDecodeError as exc:
                logger.warning(
                    "COURTROOM_ROLE_MODEL_MAP parse failed; using defaults",
                    error=str(exc),
                )

        if role_override_map:
            merged = dict(raw_map)
            for role, chains in role_override_map.items():
                merged[str(role)] = chains
            raw_map = merged

        final_map: dict[str, list[ModelRoute]] = {}
        for role, routes in raw_map.items():
            built: list[ModelRoute] = []
            if not isinstance(routes, list):
                continue
            for item in routes:
                if not isinstance(item, dict):
                    continue
                provider = str(item.get("provider", "")).strip().lower()
                model = str(item.get("model", "")).strip()
                if provider == "gemini":
                    provider = "google"
                if not provider or not model:
                    continue
                if provider not in self.available_providers:
                    continue
                built.append(ModelRoute(provider=provider, model=model))

            if built:
                final_map[role] = built

        return final_map

    def get_chain(self, role_name: str) -> list[ModelRoute]:
        """Return ordered model fallback chain for role."""
        return list(self._role_map.get(role_name, []))
