"""Google GenAI-backed LLM client implementation."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

from shared.llm.clients.base import LLMClient

load_dotenv()

logger = logging.getLogger(__name__)


def _model_priority() -> List[str]:
    raw = os.getenv("GEMINI_MODEL_PRIORITY")
    if raw:
        models = [item.strip() for item in raw.split(",") if item.strip()]
        if models:
            return models
    primary = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
    fallback = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash")
    if primary == fallback:
        return [primary]
    return [primary, fallback]


@dataclass
class GeminiConfig:
    model_priority: List[str] = field(default_factory=_model_priority)
    api_key: str | None = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    temperature: float = 0.7
    max_output_tokens: int = 2048


class GeminiLLMClient(LLMClient):
    """Thread-safe Gemini client using google-genai."""

    def __init__(self, config: GeminiConfig | None = None) -> None:
        self.config = config or GeminiConfig()
        self._client: genai.Client | None = None
        self._active_model_name: str | None = None
        self._initialized = False

    # ------------------------------------------------------------------ setup
    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        client_kwargs = {}
        if self.config.api_key:
            client_kwargs["api_key"] = self.config.api_key

        self._client = genai.Client(**client_kwargs)
        self._active_model_name = self.config.model_priority[0]
        self._initialized = True
        logger.info(
            "Gemini client initialized with priority order: %s",
            ", ".join(self.config.model_priority),
        )

    # ------------------------------------------------------------------ helpers
    def _log_rate_limits(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage:
            logger.info(
                "Gemini usage - prompt_tokens=%s, candidates=%s, total=%s",
                usage.prompt_token_count,
                usage.candidates_token_count,
                usage.total_token_count,
            )

        raw_response = getattr(response, "_response", None)
        if not raw_response:
            return
        http_response = getattr(raw_response, "response", None)
        headers = getattr(http_response, "headers", None) if http_response else None
        if not headers:
            return
        rate_headers = {
            k: v for k, v in headers.items() if k.lower().startswith("x-ratelimit")
        }
        if rate_headers:
            logger.info("Gemini rate limits: %s", rate_headers)

    def _generation_config(self) -> genai_types.GenerateContentConfig:
        return genai_types.GenerateContentConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
        )

    def _select_model_name(self) -> str:
        if self._active_model_name:
            return self._active_model_name
        return self.config.model_priority[0]

    def _format_messages(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            formatted.append(
                {
                    "role": msg["role"],
                    "parts": [{"text": msg["content"]}],
                }
            )
        return formatted

    def _convert_tools(self, tools: list[dict]) -> list[genai_types.Tool] | None:
        if not tools:
            return None
        declarations: list[genai_types.FunctionDeclaration] = []
        for tool in tools:
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description"),
                    parameters=tool.get("parameters"),
                )
            )
        return [genai_types.Tool(function_declarations=declarations)]

    def _retry_with_backoff(self, func: Callable[[], Any]) -> Any:
        delay = self.config.base_delay
        for attempt in range(self.config.max_retries):
            try:
                return func()
            except Exception as exc:  # pragma: no cover - depends on SDK
                error_str = str(exc).lower()
                if any(
                    term in error_str for term in ["rate", "quota", "429", "503"]
                ) and attempt < (self.config.max_retries - 1):
                    logger.warning(
                        "Rate limited, retrying in %ss (attempt %s)", delay, attempt + 1
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, self.config.max_delay)
                    continue
                raise
        raise RuntimeError(f"Max retries ({self.config.max_retries}) exceeded")

    # ------------------------------------------------------------------ interface
    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        self._ensure_initialized()

        def _generate():
            kwargs = {
                "model": self._select_model_name(),
                "contents": prompt,
                "config": self._generation_config(),
            }
            if system_instruction:
                kwargs["system_instruction"] = system_instruction
            response = self._client.models.generate_content(**kwargs)  # type: ignore[call-arg]
            self._log_rate_limits(response)
            return response.text

        return self._retry_with_backoff(_generate)

    def chat(
        self, messages: list[dict[str, str]], system_instruction: str | None = None
    ) -> str:
        self._ensure_initialized()

        def _chat():
            kwargs = {
                "model": self._select_model_name(),
                "contents": self._format_messages(messages),
                "config": self._generation_config(),
            }
            if system_instruction:
                kwargs["system_instruction"] = system_instruction
            response = self._client.models.generate_content(**kwargs)  # type: ignore[call-arg]
            self._log_rate_limits(response)
            return response.text

        return self._retry_with_backoff(_chat)

    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_instruction: str | None = None,
    ) -> dict:
        self._ensure_initialized()

        def _generate_with_tools():
            config = self._generation_config()
            converted_tools = self._convert_tools(tools)
            if converted_tools:
                config.tools = converted_tools  # type: ignore[attr-defined]
            kwargs = {
                "model": self._select_model_name(),
                "contents": prompt,
                "config": config,
            }
            if system_instruction:
                kwargs["system_instruction"] = system_instruction
            response = self._client.models.generate_content(**kwargs)  # type: ignore[call-arg]

            candidates = getattr(response, "candidates", None)
            candidate = candidates[0] if candidates else None
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts:
                for part in parts:
                    function_call = getattr(part, "function_call", None)
                    if function_call:
                        return {
                            "function_call": {
                                "name": function_call.name,
                                "args": dict(function_call.args),
                            }
                        }

            self._log_rate_limits(response)
            return {"text": response.text}

        return self._retry_with_backoff(_generate_with_tools)

    # ------------------------------------------------------------------ misc
    def raw_client(self) -> genai.Client | None:
        self._ensure_initialized()
        return self._client


_client_singleton: GeminiLLMClient | None = None


def get_client() -> GeminiLLMClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = GeminiLLMClient()
    return _client_singleton
