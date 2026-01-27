"""Compatibility shim for multi-turn goal clarification agent.

Canonical orchestration lives in `application.services.goal_clarification_service`.
This module preserves test monkeypatch seams:
- `modules.values.agent.chat`
"""

from __future__ import annotations

from typing import Optional

from shared.llm.gateway import chat
from shared.llm.prompts import VALUES_CLARIFICATION_PROMPT
from application.services.goal_clarification_service import GoalClarificationService
from modules.values.domain import GoalClarificationState


class GoalClarificationAgent:
    """Guides the user through goal clarification before commerce."""

    min_questions: int = 2
    max_questions: int = 3

    def __init__(self) -> None:
        self._service = GoalClarificationService(
            chat_fn=chat, prompt_template=VALUES_CLARIFICATION_PROMPT
        )

    def continue_dialogue(
        self,
        state: GoalClarificationState,
        user_message: str,
        context: Optional[str] = None,
    ) -> GoalClarificationState:
        return self._service.continue_dialogue(
            state=state, user_message=user_message, context=context
        )

    def start(
        self,
        query: str,
        metadata: Optional[dict] = None,
        context: Optional[str] = None,
    ) -> GoalClarificationState:
        return self._service.start(query=query, metadata=metadata, context=context)


__all__ = ["GoalClarificationAgent"]
