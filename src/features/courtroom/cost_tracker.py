"""Cost and token estimation utilities for courtroom runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostEvent:
    """Single estimated usage event."""

    category: str
    provider: str
    model: str
    tokens: int
    estimated_cost_usd: float


class CourtroomCostTracker:
    """Accumulate estimated token usage and cost across courtroom stages."""

    # rough per-1K token estimates (USD), intentionally conservative
    RATE_PER_1K = {
        "openai": 0.001,
        "google": 0.0007,
        "groq": 0.0003,
        "fallback": 0.0,
    }

    def __init__(self) -> None:
        self.events: list[CostEvent] = []

    def add_event(self, *, category: str, provider: str, model: str, text: str) -> None:
        """Estimate token usage/cost for a text-producing event."""
        tokens = self._estimate_tokens(text)
        rate = self.RATE_PER_1K.get(provider, 0.001)
        cost = (tokens / 1000.0) * rate
        self.events.append(
            CostEvent(
                category=category,
                provider=provider,
                model=model,
                tokens=tokens,
                estimated_cost_usd=round(cost, 6),
            )
        )

    def add_scalar_event(
        self,
        *,
        category: str,
        provider: str,
        model: str,
        tokens: int,
    ) -> None:
        """Add non-text event by explicit token estimate."""
        tokens = max(0, int(tokens))
        rate = self.RATE_PER_1K.get(provider, 0.001)
        cost = (tokens / 1000.0) * rate
        self.events.append(
            CostEvent(
                category=category,
                provider=provider,
                model=model,
                tokens=tokens,
                estimated_cost_usd=round(cost, 6),
            )
        )

    def total_tokens(self) -> int:
        """Total estimated tokens."""
        return sum(e.tokens for e in self.events)

    def total_cost(self) -> float:
        """Total estimated cost in USD."""
        return round(sum(e.estimated_cost_usd for e in self.events), 4)

    def by_category(self) -> dict[str, dict[str, float | int]]:
        """Category-level usage summary."""
        summary: dict[str, dict[str, float | int]] = {}
        for e in self.events:
            bucket = summary.setdefault(
                e.category,
                {"tokens": 0, "estimated_cost_usd": 0.0, "events": 0},
            )
            bucket["tokens"] = int(bucket["tokens"]) + e.tokens
            bucket["estimated_cost_usd"] = round(
                float(bucket["estimated_cost_usd"]) + e.estimated_cost_usd,
                4,
            )
            bucket["events"] = int(bucket["events"]) + 1
        return summary

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        words = len((text or "").split())
        return max(1, int(words * 1.35))
