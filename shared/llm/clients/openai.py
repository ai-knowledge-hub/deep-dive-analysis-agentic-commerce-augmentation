"""OpenAI-backed LLM client implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests

from shared.config.env import get_settings
from shared.llm.clients.base import LLMClient

OPENAI_API_BASE = "https://api.openai.com/v1/chat/completions"


@dataclass
class OpenAIConfig:
    api_key: str | None = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1024

    @classmethod
    def from_settings(cls) -> "OpenAIConfig":
        settings = get_settings()
        return cls(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=float(settings.openai_temperature),
            max_tokens=int(settings.openai_max_tokens),
        )


class OpenAILLMClient(LLMClient):
    def __init__(self, config: OpenAIConfig | None = None) -> None:
        self.config = config or OpenAIConfig.from_settings()
        if not self.config.api_key:
            raise ValueError(
                "OPENAI_API_KEY must be set when using LLM_PROVIDER=openai"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = requests.post(
            OPENAI_API_BASE, headers=self._headers(), json=payload, timeout=60
        )
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"OpenAI error {response.status_code}: {response.text}",
                response=response,
            )
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        content = choices[0].get("message", {}).get("content")
        return content or ""

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        return self._request(messages)

    def chat(
        self, messages: list[dict[str, str]], system_instruction: str | None = None
    ) -> str:
        openai_messages = []
        if system_instruction:
            openai_messages.append({"role": "system", "content": system_instruction})
        openai_messages.extend(messages)
        return self._request(openai_messages)

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


_openai_client: Optional[OpenAILLMClient] = None


def get_client() -> OpenAILLMClient:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAILLMClient()
    return _openai_client


def reset_client() -> None:
    global _openai_client
    _openai_client = None


__all__ = ["OpenAILLMClient", "get_client", "reset_client", "OpenAIConfig"]
