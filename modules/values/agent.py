"""Multi-turn values clarification agent."""

from __future__ import annotations

from typing import List, Optional

from shared.llm.gateway import chat
from shared.llm.prompts import VALUES_CLARIFICATION_PROMPT
from modules.values.domain import ClarificationState


class ValuesAgent:
    """Guides the user through World B values clarification before commerce."""

    min_questions: int = 2

    def start(
        self,
        query: str,
        metadata: Optional[dict] = None,
        context: Optional[str] = None,
    ) -> ClarificationState:
        """Start a new clarification dialogue."""
        state = ClarificationState(query=query, metadata=metadata or {})
        prompt = f"User request: {query}\nRespond per instructions."
        response = chat(
            messages=[{"role": "user", "content": prompt}],
            system_instruction=self._system_prompt(context),
        )
        state.add_turn("user", query)
        state.add_turn("agent", response.strip())
        return state

    def continue_dialogue(
        self,
        state: ClarificationState,
        user_message: str,
        context: Optional[str] = None,
    ) -> ClarificationState:
        """Continue an existing dialogue."""
        history = [
            {"role": turn.speaker, "content": turn.content} for turn in state.turns
        ]
        history.append({"role": "user", "content": user_message})
        response = chat(
            messages=history,
            system_instruction=self._system_prompt(context),
        )
        state.add_turn("user", user_message)
        state.add_turn("agent", response.strip())
        if self._has_summary(response):
            state.extracted_goals = self._extract_goals(response)
            state.ready_for_products = True
        return state

    def _system_prompt(self, context: Optional[str]) -> str:
        """Build the system prompt with optional context."""
        if not context:
            return VALUES_CLARIFICATION_PROMPT
        return f"{VALUES_CLARIFICATION_PROMPT}\n\nSession context:\n{context}"

    def _has_summary(self, agent_response: str) -> bool:
        """Check if the agent response contains a summary."""
        return (
            "does that capture" in agent_response.lower()
            or "summary" in agent_response.lower()
        )

    def _extract_goals(self, agent_response: str) -> List[str]:
        """Extract goals from the agent's summary response."""
        # Simple heuristic: collect bullet/numbered list lines.
        goals: List[str] = []
        for line in agent_response.splitlines():
            stripped = line.strip("- ").strip()
            if stripped and any(
                keyword in stripped.lower()
                for keyword in ["goal", "reduce", "enable", "budget"]
            ):
                goals.append(stripped)
        return goals or [agent_response.strip()]


__all__ = ["ValuesAgent"]
