"""Infrastructure adapter for goal clarification (LLM chat + parsing).

The pure state machine lives in `domain.values.types`.
The orchestration lives in `application.services.goal_clarification_service`.
This adapter binds LLM + prompts and exposes the legacy agent interface used by
API routes (`start`, `continue_dialogue`).
"""

from __future__ import annotations

from typing import Any, Dict

from application.services.goal_clarification_service import GoalClarificationService
from domain.values.types import GoalClarificationState
from infrastructure.llm.gateway import chat
from infrastructure.llm.prompts import VALUES_CLARIFICATION_PROMPT


class GoalClarificationAgent:
    def __init__(self) -> None:
        self._service = GoalClarificationService(
            chat_fn=chat, prompt_template=VALUES_CLARIFICATION_PROMPT
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
