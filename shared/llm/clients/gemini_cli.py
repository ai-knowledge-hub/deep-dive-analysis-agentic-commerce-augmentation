"""Gemini CLI-backed LLM client implementation (dev-only)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List

from shared.config.env import settings
from shared.llm.clients.base import LLMClient

NO_TOOLS_INSTRUCTION = (
    "Do not call tools or functions. Do not use tool syntax. "
    "Respond with plain text only."
)
CLI_TOOLS_INSTRUCTION = (
    "You may use the following tools if needed: "
    "GoogleSearch, WebFetch, Shell, ReadFile, ReadFolder, ReadManyFiles, "
    "SearchText, FindFiles, Edit, WriteFile, Save Memory. "
    "Use ONLY these tool names. Do NOT use run_shell_command or other tool names."
)


def _ensure_dev_only() -> None:
    if settings.app_env not in {"local", "dev"}:
        raise RuntimeError("Gemini CLI provider is dev-only. Set APP_ENV=local/dev.")


def _select_model() -> str:
    return (
        os.getenv("GEMINI_CLI_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
    )


def _max_system_chars() -> int:
    return int(os.getenv("GEMINI_CLI_MAX_SYSTEM_CHARS", "1800"))


def _allow_tools() -> bool:
    return os.getenv("GEMINI_CLI_ALLOW_TOOLS", "0").lower() in {"1", "true", "yes"}


def _build_prompt(
    messages: List[dict[str, str]],
    system_instruction: str | None,
    *,
    allow_tools: bool,
) -> str:
    parts: List[str] = []
    header_parts: List[str] = []
    if system_instruction:
        header_parts.append(system_instruction.strip()[: _max_system_chars()])
    header_parts.append(CLI_TOOLS_INSTRUCTION if allow_tools else NO_TOOLS_INSTRUCTION)
    parts.append("\n\n".join([p for p in header_parts if p]))
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role.upper()}: {content}")
    return "\n\n".join([p for p in parts if p])


@dataclass
class GeminiCLIConfig:
    model: str = _select_model()
    timeout_s: int = int(os.getenv("GEMINI_CLI_TIMEOUT_S", "45"))


class GeminiCLILLMClient(LLMClient):
    """Gemini CLI-backed client for local development."""

    def __init__(self, config: GeminiCLIConfig | None = None) -> None:
        _ensure_dev_only()
        self.config = config or GeminiCLIConfig()

    def _run(self, prompt: str) -> str:
        args = ["gemini", "-m", self.config.model, "-p", prompt]
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_s,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Gemini CLI error ({result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        header = (
            system_instruction.strip()[: _max_system_chars()]
            if system_instruction
            else ""
        )
        tool_line = NO_TOOLS_INSTRUCTION
        combined = "\n\n".join([p for p in [header, tool_line, prompt] if p])
        try:
            return self._run(combined)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Gemini CLI timed out. "
                "Try GEMINI_CLI_MODEL=gemini-2.0-flash or increase GEMINI_CLI_TIMEOUT_S. "
                "Also ensure `gemini` CLI is authenticated."
            ) from exc

    def chat(
        self, messages: list[dict[str, str]], system_instruction: str | None = None
    ) -> str:
        prompt = _build_prompt(messages, system_instruction, allow_tools=False)
        try:
            return self._run(prompt)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Gemini CLI timed out. "
                "Try GEMINI_CLI_MODEL=gemini-2.0-flash or increase GEMINI_CLI_TIMEOUT_S. "
                "Also ensure `gemini` CLI is authenticated."
            ) from exc

    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_instruction: str | None = None,
    ) -> dict:
        # Gemini CLI does not expose tool calling; return plain text response.
        header = (
            system_instruction.strip()[: _max_system_chars()]
            if system_instruction
            else ""
        )
        tool_line = CLI_TOOLS_INSTRUCTION if _allow_tools() else NO_TOOLS_INSTRUCTION
        combined = "\n\n".join([p for p in [header, tool_line, prompt] if p])
        try:
            text = self._run(combined)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Gemini CLI timed out. "
                "Try GEMINI_CLI_MODEL=gemini-2.0-flash or increase GEMINI_CLI_TIMEOUT_S. "
                "Also ensure `gemini` CLI is authenticated."
            ) from exc
        return {"content": text}

    def raw_client(self) -> None:
        # CLI-backed client has no underlying SDK object to expose.
        return None


_client_singleton: GeminiCLILLMClient | None = None


def get_client() -> GeminiCLILLMClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = GeminiCLILLMClient()
    return _client_singleton


__all__ = ["GeminiCLILLMClient", "get_client"]
