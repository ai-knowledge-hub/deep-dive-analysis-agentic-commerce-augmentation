"""LLM client factory and provider resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.env import settings
from llm.clients.base import LLMClient
from llm.clients.openrouter import OpenRouterLLMClient, get_client as get_openrouter_client

if TYPE_CHECKING:  # pragma: no cover - only for type hints
    from llm.clients.gemini import GeminiLLMClient


def _get_gemini_client() -> "GeminiLLMClient":
    from llm.clients.gemini import get_client as get_gemini_client

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
    "get_llm_client",
]
