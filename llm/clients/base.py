"""Shared abstractions for LLM client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Minimal interface for generation-capable LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system_instruction: str | None = None) -> str: ...

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], system_instruction: str | None = None) -> str: ...

    @abstractmethod
    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_instruction: str | None = None,
    ) -> dict: ...

    @abstractmethod
    def raw_client(self) -> Any: ...
