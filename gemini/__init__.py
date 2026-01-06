"""Gemini integration module for empowerment-focused commerce.

This module provides the Gemini-powered agents that implement the values
clarification dialogue, semantic intent classification, and transparent
product reasoning that differentiates World B from World A commerce.
"""

from __future__ import annotations

from llm.clients.gemini import GeminiLLMClient as GeminiClient
from llm.prompts import (
    VALUES_CLARIFICATION_PROMPT,
    PRODUCT_REASONING_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
)
from llm.gateway import (
    chat as gateway_chat,
    generate as gateway_generate,
    generate_with_tools as gateway_generate_with_tools,
    raw_client as gateway_raw_client,
)


def generate(prompt: str, system_instruction: str | None = None) -> str:
    return gateway_generate(prompt, system_instruction, provider="gemini")


def chat(messages: list[dict[str, str]], system_instruction: str | None = None) -> str:
    return gateway_chat(messages, system_instruction, provider="gemini")


def generate_with_tools(
    prompt: str,
    tools: list[dict],
    system_instruction: str | None = None,
) -> dict:
    return gateway_generate_with_tools(prompt, tools, system_instruction, provider="gemini")


def get_model():
    return gateway_raw_client(provider="gemini")

__all__ = [
    "get_model",
    "chat",
    "generate",
    "GeminiClient",
    "VALUES_CLARIFICATION_PROMPT",
    "PRODUCT_REASONING_PROMPT",
    "INTENT_CLASSIFICATION_PROMPT",
    "generate_with_tools",
]
