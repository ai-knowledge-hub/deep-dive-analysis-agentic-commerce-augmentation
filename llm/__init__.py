"""Model-agnostic LLM utilities (prompts, tools, clients)."""

from __future__ import annotations

from llm.gateway import (
    chat,
    generate,
    generate_with_tools,
    get_llm_client,
    raw_client,
)

__all__ = [
    "prompts",
    "tools",
    "get_llm_client",
    "generate",
    "chat",
    "generate_with_tools",
    "raw_client",
]
