"""Provider-agnostic helpers for accessing LLM clients."""

from __future__ import annotations

from typing import Any

from shared.llm.clients import LLMClient, get_llm_client as _get_llm_client


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Return an LLM client for the requested provider (default from env)."""
    return _get_llm_client(provider)


def generate(prompt: str, system_instruction: str | None = None, provider: str | None = None) -> str:
    """Single-turn generation via the configured LLM."""
    client = get_llm_client(provider)
    return client.generate(prompt, system_instruction)


def chat(
    messages: list[dict[str, str]],
    system_instruction: str | None = None,
    provider: str | None = None,
) -> str:
    """Multi-turn chat via the configured LLM."""
    client = get_llm_client(provider)
    return client.chat(messages, system_instruction)


def generate_with_tools(
    prompt: str,
    tools: list[dict],
    system_instruction: str | None = None,
    provider: str | None = None,
) -> dict:
    """Generate content that may include tool calls."""
    client = get_llm_client(provider)
    return client.generate_with_tools(prompt, tools, system_instruction)


def raw_client(provider: str | None = None) -> Any:
    """Return the underlying provider-specific client."""
    client = get_llm_client(provider)
    return client.raw_client()
