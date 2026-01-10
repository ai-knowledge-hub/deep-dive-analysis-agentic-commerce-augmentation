"""LLM client factory and provider resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.config.env import settings
from shared.llm.clients.base import LLMClient
from shared.llm.clients.openrouter import (
    OpenRouterLLMClient,
    get_client as get_openrouter_client,
)

if TYPE_CHECKING:  # pragma: no cover - only for type hints
    from shared.llm.clients.gemini import GeminiLLMClient


def _get_gemini_client() -> "GeminiLLMClient":
    from shared.llm.clients.gemini import get_client as get_gemini_client

    return get_gemini_client()


def get_llm_client(provider: str | None = None) -> LLMClient:
    provider_name = (provider or settings.llm_provider).lower()
    if provider_name == "gemini":
        return _get_gemini_client()
    if provider_name == "openrouter":
        return get_openrouter_client()
    raise ValueError(f"Unsupported LLM provider: {provider_name}")


__all__ = [
    "LLMClient",
    "OpenRouterLLMClient",
    "get_llm_client",
]
