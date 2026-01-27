"""Application service for goal clarification (multi-turn).

Orchestrates prompts + parsing while keeping parsing heuristics pure in domain.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from domain.values.extraction import extract_goals, fallback_goals, has_summary
from domain.values.types import GoalClarificationState


ChatFn = Callable[..., str]


class GoalClarificationService:
    min_questions: int = 2
    max_questions: int = 3

    def __init__(self, *, chat_fn: ChatFn, prompt_template: str) -> None:
        self._chat_fn = chat_fn
        self._prompt_template = prompt_template

    def start(
        self,
        *,
        query: str,
        metadata: Optional[dict] = None,
        context: Optional[str] = None,
    ) -> GoalClarificationState:
        state = GoalClarificationState(query=query, metadata=metadata or {})
        prompt = f"User request: {query}\nRespond per instructions."
        response = self._chat_fn(
            messages=[{"role": "user", "content": prompt}],
            system_instruction=self._system_prompt(context),
        )
        state.add_turn("user", query)
        state.add_turn("agent", response.strip())
        return state

    def continue_dialogue(
        self,
        *,
        state: GoalClarificationState,
        user_message: str,
        context: Optional[str] = None,
    ) -> GoalClarificationState:
        history: List[dict] = [
            {"role": turn.speaker, "content": turn.content} for turn in state.turns
        ]
        history.append({"role": "user", "content": user_message})
        response = self._chat_fn(
            messages=history,
            system_instruction=self._system_prompt(context),
        )
        state.add_turn("user", user_message)
        state.add_turn("agent", response.strip())
        goals = extract_goals(response)
        agent_turns = len([turn for turn in state.turns if turn.speaker == "agent"])
        if (
            has_summary(response)
            or (agent_turns >= self.min_questions and goals)
            or agent_turns >= self.max_questions
        ):
            if not goals:
                goals = fallback_goals(state)
            state.extracted_goals = goals
            state.ready_for_products = True
        return state

    def _system_prompt(self, context: Optional[str]) -> str:
        if not context:
            return self._prompt_template
        return f"{self._prompt_template}\n\nSession context:\n{context}"


__all__ = ["GoalClarificationService", "ChatFn"]

