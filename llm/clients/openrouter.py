"""OpenRouter-backed LLM client for local/testing usage."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import requests

from llm.clients.base import LLMClient

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class OpenRouterConfig:
    api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    model: str = os.getenv("OPENROUTER_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    temperature: float = float(os.getenv("OPENROUTER_TEMPERATURE", "0.3"))
    max_tokens: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "1024"))


class OpenRouterLLMClient(LLMClient):
    """Minimal OpenRouter client that hits the chat completions endpoint."""

    def __init__(self, config: OpenRouterConfig | None = None) -> None:
        self.config = config or OpenRouterConfig()
        if not self.config.api_key:
            raise ValueError("OPENROUTER_API_KEY must be set when using LLM_PROVIDER=openrouter")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "Agentic Commerce Dev"),
        }

    def _request(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = requests.post(OPENROUTER_API_BASE, headers=self._headers(), data=json.dumps(payload), timeout=60)
        response.raise_for_status()
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

    def chat(self, messages: list[dict[str, str]], system_instruction: str | None = None) -> str:
        openrouter_messages = []
        if system_instruction:
            openrouter_messages.append({"role": "system", "content": system_instruction})
        openrouter_messages.extend(messages)
        return self._request(openrouter_messages)

    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_instruction: str | None = None,
    ) -> dict:
        # Basic implementation: just include tool descriptions in the prompt.
        tool_descriptions = "\n".join(f"{tool['name']}: {tool.get('description','')}" for tool in tools)
        full_prompt = prompt
        if tool_descriptions:
            full_prompt = f"{tool_descriptions}\n\n{prompt}"
        text = self.generate(full_prompt, system_instruction=system_instruction)
        return {"text": text}

    def raw_client(self) -> Any:
        return None


_openrouter_client: Optional[OpenRouterLLMClient] = None


def get_client() -> OpenRouterLLMClient:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterLLMClient()
    return _openrouter_client
