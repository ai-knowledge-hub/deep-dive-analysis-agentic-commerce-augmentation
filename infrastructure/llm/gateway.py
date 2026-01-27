"""Infrastructure wrapper for LLM gateway helpers.

Canonical implementation currently lives in `shared.llm.gateway`.
This module exists to keep application code from depending on `shared/*` directly.
"""

from __future__ import annotations

from typing import Any

from shared.llm.gateway import (
    chat as _chat,
    generate as _generate,
    generate_with_tools as _generate_with_tools,
)


def generate(
    prompt: str, system_instruction: str | None = None, provider: str | None = None
) -> str:
    return _generate(prompt, system_instruction=system_instruction, provider=provider)


def chat(
    messages: list[dict[str, str]],
    system_instruction: str | None = None,
    provider: str | None = None,
) -> str:
    return _chat(messages, system_instruction=system_instruction, provider=provider)


def generate_with_tools(
    prompt: str,
    tools: list[dict],
    system_instruction: str | None = None,
    provider: str | None = None,
) -> dict:
    return _generate_with_tools(
        prompt=prompt, tools=tools, system_instruction=system_instruction, provider=provider
    )


def raw_client(provider: str | None = None) -> Any:
    # keep narrow surface; callers can still access raw if needed
    from shared.llm.gateway import raw_client as _raw_client

    return _raw_client(provider)


__all__ = ["generate", "chat", "generate_with_tools", "raw_client"]
