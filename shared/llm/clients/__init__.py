"""LLM client factory and provider resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.config.env import get_settings
from shared.llm.clients.base import LLMClient
from shared.llm.clients.openrouter import (
    OpenRouterLLMClient,
    get_client as get_openrouter_client,
)
from shared.llm.clients.openai import OpenAILLMClient, get_client as get_openai_client
from shared.llm.clients.anthropic import (
    AnthropicLLMClient,
    get_client as get_anthropic_client,
)

if TYPE_CHECKING:  # pragma: no cover - only for type hints
    from shared.llm.clients.gemini import GeminiLLMClient
    from shared.llm.clients.gemini_cli import GeminiCLILLMClient


def _get_gemini_client() -> "GeminiLLMClient":
    from shared.llm.clients.gemini import get_client as get_gemini_client

    return get_gemini_client()


def _get_gemini_cli_client() -> "GeminiCLILLMClient":
    from shared.llm.clients.gemini_cli import get_client as get_gemini_cli_client

    return get_gemini_cli_client()


def get_llm_client(provider: str | None = None) -> LLMClient:
    settings = get_settings()
    provider_name = (provider or settings.llm_provider).lower()
    if provider_name == "openai":
        return get_openai_client()
    if provider_name in {"anthropic", "claude"}:
        return get_anthropic_client()
    if provider_name == "gemini":
        return _get_gemini_client()
    if provider_name in {"gemini_cli", "gemini-cli"}:
        return _get_gemini_cli_client()
    if provider_name == "openrouter":
        return get_openrouter_client()
    raise ValueError(f"Unsupported LLM provider: {provider_name}")


def reset_clients() -> None:
    from shared.llm.clients.openai import reset_client as reset_openai
    from shared.llm.clients.anthropic import reset_client as reset_anthropic
    from shared.llm.clients.openrouter import reset_client as reset_openrouter
    from shared.llm.clients.gemini import reset_client as reset_gemini

    reset_openai()
    reset_anthropic()
    reset_openrouter()
    reset_gemini()


__all__ = [
    "LLMClient",
    "OpenRouterLLMClient",
    "OpenAILLMClient",
    "AnthropicLLMClient",
    "get_llm_client",
    "reset_clients",
]
