"""Single-model routing for every courtroom participant, including the judge."""

from dataclasses import dataclass

from src.config.settings import settings


@dataclass(frozen=True)
class ModelRoute:
    """Configured courtroom model route."""

    provider: str
    model: str


class CourtroomModelRegistry:
    """Use the configured OpenAI extraction model without provider fallthrough."""

    def __init__(self, role_override_map=None) -> None:
        model = settings.extraction_model.strip()
        # The shared client uses legacy max_tokens and temperature parameters.
        if not model.startswith(("gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-3.5-turbo")):
            model = "gpt-4o-mini"
        self.route = ModelRoute(provider="openai", model=model)

    def get_chain(self, role_name: str) -> list[ModelRoute]:
        """Role overrides cannot break the shared-model invariant."""
        return [self.route] if settings.openai_api_key else []
