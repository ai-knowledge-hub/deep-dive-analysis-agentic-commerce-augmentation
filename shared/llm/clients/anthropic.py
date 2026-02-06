"""Anthropic-backed LLM client implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests

from shared.config.env import get_settings
from shared.llm.clients.base import LLMClient

ANTHROPIC_API_BASE = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


@dataclass
class AnthropicConfig:
    api_key: str | None = None
    model: str = "claude-3-5-sonnet-20240620"
    temperature: float = 0.3
    max_tokens: int = 1024

    @classmethod
    def from_settings(cls) -> "AnthropicConfig":
        settings = get_settings()
        return cls(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            temperature=float(settings.anthropic_temperature),
            max_tokens=int(settings.anthropic_max_tokens),
        )


class AnthropicLLMClient(LLMClient):
    def __init__(self, config: AnthropicConfig | None = None) -> None:
        self.config = config or AnthropicConfig.from_settings()
        if not self.config.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set when using LLM_PROVIDER=anthropic"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.config.api_key or "",
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, messages: list[dict[str, str]], system: str | None) -> str:
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        response = requests.post(
            ANTHROPIC_API_BASE, headers=self._headers(), json=payload, timeout=60
        )
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"Anthropic error {response.status_code}: {response.text}",
                response=response,
            )
        data = response.json()
        content = data.get("content") or []
        if not content:
            return ""
        first = content[0]
        if isinstance(first, dict):
            return first.get("text") or ""
        return ""

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, system_instruction)

    def chat(
        self, messages: list[dict[str, str]], system_instruction: str | None = None
    ) -> str:
        return self._request(messages, system_instruction)

    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_instruction: str | None = None,
    ) -> dict:
        tool_descriptions = "\n".join(
            f"{tool['name']}: {tool.get('description', '')}"
            for tool in tools
            if "name" in tool
        )
        full_prompt = (
            f"{tool_descriptions}\n\n{prompt}" if tool_descriptions else prompt
        )
        text = self.generate(full_prompt, system_instruction=system_instruction)
        return {"text": text}

    def raw_client(self) -> Any:
        return None


_anthropic_client: Optional[AnthropicLLMClient] = None


def get_client() -> AnthropicLLMClient:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AnthropicLLMClient()
    return _anthropic_client


def reset_client() -> None:
    global _anthropic_client
    _anthropic_client = None


__all__ = ["AnthropicLLMClient", "get_client", "reset_client", "AnthropicConfig"]
