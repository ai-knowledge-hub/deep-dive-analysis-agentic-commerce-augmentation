"""Provider-agnostic helpers for accessing LLM clients and embeddings."""

from __future__ import annotations

from typing import Any, List

from shared.llm.clients import LLMClient, get_llm_client as _get_llm_client
from shared.llm.embeddings import (
    embed as _embed,
    embed_batch as _embed_batch,
    similarity as _similarity,
    get_embedding_provider as _get_embedding_provider,
)


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Return an LLM client for the requested provider (default from env)."""
    return _get_llm_client(provider)


def generate(
    prompt: str, system_instruction: str | None = None, provider: str | None = None
) -> str:
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


# -----------------------------------------------------------------------------
# Embedding Functions
# -----------------------------------------------------------------------------


def embed(text: str) -> List[float]:
    """Generate embedding for text using configured provider (Gemini + local fallback)."""
    return _embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    return _embed_batch(texts)


def semantic_similarity(text_a: str, text_b: str) -> float:
    """Compute semantic similarity between two texts (0.0 to 1.0)."""
    return _similarity(text_a, text_b)


def get_embedding_provider():
    """Return the active embedding provider."""
    return _get_embedding_provider()
