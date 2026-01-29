from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PromptBudget:
    max_context_chars: int = 2000
    max_prompt_chars: int = 12000


class ContextManager:
    def __init__(self, *, budget: Optional[PromptBudget] = None) -> None:
        self.budget = budget or PromptBudget()

    def trim(self, text: str, *, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "…"

    def research_prompt(
        self,
        *,
        template: str,
        query: str,
        goals_block: str,
        context: Optional[str],
    ) -> str:
        context_block = context or ""
        context_block = self.trim(
            context_block, max_chars=self.budget.max_context_chars
        )
        prompt = template.format(
            query=query, goals_block=goals_block, context=context_block
        )
        return self.trim(prompt, max_chars=self.budget.max_prompt_chars)


__all__ = ["ContextManager", "PromptBudget"]
