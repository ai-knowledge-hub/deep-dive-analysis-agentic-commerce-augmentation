"""LLM client factory and provider resolution."""

from __future__ import annotations

import os

from llm.clients.base import LLMClient
from llm.clients.gemini import GeminiLLMClient, get_client as get_gemini_client
from llm.clients.openrouter import OpenRouterLLMClient, get_client as get_openrouter_client


def get_llm_client(provider: str | None = None) -> LLMClient:
    provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
    if provider == "gemini":
        return get_gemini_client()
    if provider == "openrouter":
        return get_openrouter_client()
    raise ValueError(f"Unsupported LLM provider: {provider}")


__all__ = [
    "LLMClient",
    "get_llm_client",
    "GeminiLLMClient",
    "OpenRouterLLMClient",
]
