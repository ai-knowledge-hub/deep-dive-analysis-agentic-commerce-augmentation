from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional


def _stable_key(*parts: str) -> str:
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def trim_text(text: str, *, max_chars: int) -> str:
    if not text:
        return ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


@dataclass
class PromptBudget:
    max_context_chars: int = 2000
    max_prompt_chars: int = 12000


class PromptCache:
    def __init__(self, *, max_items: int = 128) -> None:
        self._max_items = max_items
        self._data: OrderedDict[str, str] = OrderedDict()

    def get(self, key: str) -> Optional[str]:
        value = self._data.get(key)
        if value is None:
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self._max_items:
            self._data.popitem(last=False)


class ContextManager:
    """Minimal context manager for prompt building.

    - Enforces a character-budget based "token budget" policy.
    - Provides a small prompt cache to avoid rebuilding prompts for identical inputs.
    """

    def __init__(self, *, budget: Optional[PromptBudget] = None) -> None:
        self.budget = budget or PromptBudget()
        self.cache = PromptCache()

    def research_prompt(
        self,
        *,
        template: str,
        query: str,
        goals_block: str,
        context: str | None,
    ) -> str:
        trimmed_context = trim_text(
            context or "", max_chars=self.budget.max_context_chars
        )
        cache_key = _stable_key(
            "research", template, query, goals_block, trimmed_context
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        context_block = (
            f"\n\nSession context:\n{trimmed_context}" if trimmed_context else ""
        )
        prompt = (
            f"{template}{context_block}\n\n"
            f"User goals:\n{goals_block}\n\n"
            f"Research query: {query}\n\n"
            "Use tools if needed, then return:\n"
            "1) Summary bullets with citations\n"
            "2) Risks/uncertainties\n"
            "3) Suggested next clarifying question"
        )

        prompt = trim_text(prompt, max_chars=self.budget.max_prompt_chars)
        self.cache.set(cache_key, prompt)
        return prompt
