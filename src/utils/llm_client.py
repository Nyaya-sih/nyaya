"""
Unified LLM client supporting multiple providers (OpenAI, Anthropic, Google).
Includes retry logic, rate limiting, and cost tracking.
"""
import json
import time
from typing import Optional, Dict, Any, List
from enum import Enum
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

from src.config.settings import settings


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMClient:
    """
    Unified interface for multiple LLM providers.
    Handles retries, rate limiting, and cost tracking.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            provider: LLM provider to use (openai/anthropic/google). Auto-detects if None.
            model: Model name to use. Uses settings.extraction_model if None.
        """
        self.provider = self._determine_provider(provider)
        self.model = model or settings.extraction_model
        self.total_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0

        # Initialize the appropriate client
        self.client = self._init_client()

        logger.info(f"LLM client initialized", provider=self.provider, model=self.model)

    def _determine_provider(self, provider: Optional[str]) -> LLMProvider:
        """Determine which provider to use based on model name or available keys."""
        if provider:
            return LLMProvider(provider.lower())

        # Auto-detect from model name
        model_lower = settings.extraction_model.lower()
        if "gpt" in model_lower or "o1" in model_lower:
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return LLMProvider.OPENAI
        elif "claude" in model_lower:
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            return LLMProvider.ANTHROPIC
        elif "gemini" in model_lower:
            if not settings.google_api_key:
                raise ValueError("Google API key not configured")
            return LLMProvider.GOOGLE

        # Default to first available
        if settings.openai_api_key:
            return LLMProvider.OPENAI
        elif settings.anthropic_api_key:
            return LLMProvider.ANTHROPIC
        elif settings.google_api_key:
            return LLMProvider.GOOGLE
        else:
            raise ValueError("No LLM API keys configured")

    def _init_client(self):
        """Initialize the appropriate LLM client."""
        if self.provider == LLMProvider.OPENAI:
            from openai import OpenAI
            return OpenAI(api_key=settings.openai_api_key)
        elif self.provider == LLMProvider.ANTHROPIC:
            from anthropic import Anthropic
            return Anthropic(api_key=settings.anthropic_api_key)
        elif self.provider == LLMProvider.GOOGLE:
            import google.generativeai as genai
            genai.configure(api_key=settings.google_api_key)
            return genai
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        response_format: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text completion from LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            temperature: Sampling temperature (uses settings default if None)
            max_tokens: Maximum tokens to generate
            response_format: Response format specification (for structured output)

        Returns:
            Generated text
        """
        temp = temperature if temperature is not None else settings.extraction_temperature
        start_time = time.time()

        try:
            if self.provider == LLMProvider.OPENAI:
                response = self._generate_openai(prompt, system_prompt, temp, max_tokens, response_format)
            elif self.provider == LLMProvider.ANTHROPIC:
                response = self._generate_anthropic(prompt, system_prompt, temp, max_tokens)
            elif self.provider == LLMProvider.GOOGLE:
                response = self._generate_google(prompt, system_prompt, temp, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            self.request_count += 1
            elapsed = time.time() - start_time

            logger.debug(
                f"LLM request completed",
                provider=self.provider,
                model=self.model,
                elapsed=f"{elapsed:.2f}s",
                request_count=self.request_count
            )

            return response

        except Exception as e:
            logger.error(f"LLM request failed", error=str(e), provider=self.provider, model=self.model)
            raise

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, Any]]
    ) -> str:
        """Generate using OpenAI API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add structured output if specified
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        # Track usage
        if hasattr(response, "usage"):
            self.total_tokens += response.usage.total_tokens
            self.total_cost += self._estimate_cost_openai(response.usage.total_tokens)

        return response.choices[0].message.content

    def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using Anthropic API."""
        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)

        # Track usage
        if hasattr(response, "usage"):
            total_tokens = response.usage.input_tokens + response.usage.output_tokens
            self.total_tokens += total_tokens
            self.total_cost += self._estimate_cost_anthropic(
                response.usage.input_tokens,
                response.usage.output_tokens
            )

        return response.content[0].text

    def _generate_google(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using Google Gemini API."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        model = self.client.GenerativeModel(self.model)
        response = model.generate_content(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
        )

        # Google API doesn't provide token counts easily, estimate roughly
        estimated_tokens = len(full_prompt.split()) + len(response.text.split())
        self.total_tokens += estimated_tokens
        self.total_cost += self._estimate_cost_google(estimated_tokens)

        return response.text

    def _estimate_cost_openai(self, tokens: int) -> float:
        """Estimate cost for OpenAI API call."""
        # Rough estimates (as of 2024) - update these as needed
        if "gpt-4o-mini" in self.model:
            return tokens * 0.00015 / 1000  # $0.15 per 1M tokens
        elif "gpt-4o" in self.model:
            return tokens * 0.005 / 1000  # $5 per 1M tokens
        elif "gpt-4" in self.model:
            return tokens * 0.03 / 1000  # $30 per 1M tokens
        else:
            return tokens * 0.0002 / 1000  # Default estimate

    def _estimate_cost_anthropic(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for Anthropic API call."""
        # Claude 3 pricing (as of 2024)
        if "opus" in self.model:
            return (input_tokens * 0.015 + output_tokens * 0.075) / 1000
        elif "sonnet" in self.model:
            return (input_tokens * 0.003 + output_tokens * 0.015) / 1000
        elif "haiku" in self.model:
            return (input_tokens * 0.00025 + output_tokens * 0.00125) / 1000
        else:
            return (input_tokens * 0.003 + output_tokens * 0.015) / 1000

    def _estimate_cost_google(self, tokens: int) -> float:
        """Estimate cost for Google Gemini API call."""
        # Gemini pricing (rough estimate)
        return tokens * 0.0001 / 1000

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "provider": self.provider,
            "model": self.model,
            "total_requests": self.request_count,
            "total_tokens": self.total_tokens,
            "estimated_cost": round(self.total_cost, 4)
        }

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self.total_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0
