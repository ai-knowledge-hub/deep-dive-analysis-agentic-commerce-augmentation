"""Goal clarification agent wrapper (application layer).

This is a small adapter around `GoalClarificationService` that keeps the agent
interface stable (`start`, `continue_dialogue`) while allowing dependency
injection from the API composition root.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from application.services.goal_clarification_service import GoalClarificationService
from domain.values.types import GoalClarificationState


class GoalClarificationAgent:
    def __init__(self, *, chat_fn: Callable[..., str], prompt_template: str) -> None:
        self._service = GoalClarificationService(
            chat_fn=chat_fn, prompt_template=prompt_template
        )

    def start(
        self, query: str, metadata: Dict[str, Any] | None = None
    ) -> GoalClarificationState:
        return self._service.start(query=query, metadata=metadata)

    def continue_dialogue(
        self, state: GoalClarificationState, message: str
    ) -> GoalClarificationState:
        return self._service.continue_dialogue(state=state, user_message=message)


__all__ = ["GoalClarificationAgent"]
