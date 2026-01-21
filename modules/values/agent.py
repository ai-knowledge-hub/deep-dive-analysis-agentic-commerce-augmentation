"""Multi-turn goal clarification agent."""

from __future__ import annotations

from typing import List, Optional

from shared.llm.gateway import chat
from shared.llm.prompts import VALUES_CLARIFICATION_PROMPT
from modules.values.domain import GoalClarificationState


class GoalClarificationAgent:
    """Guides the user through goal clarification before commerce."""

    min_questions: int = 2
    max_questions: int = 3

    def start(
        self,
        query: str,
        metadata: Optional[dict] = None,
        context: Optional[str] = None,
    ) -> GoalClarificationState:
        """Start a new clarification dialogue."""
        state = GoalClarificationState(query=query, metadata=metadata or {})
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
        state: GoalClarificationState,
        user_message: str,
        context: Optional[str] = None,
    ) -> GoalClarificationState:
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
        goals = self._extract_goals(response)
        agent_turns = len([turn for turn in state.turns if turn.speaker == "agent"])
        if (
            self._has_summary(response)
            or (agent_turns >= self.min_questions and goals)
            or agent_turns >= self.max_questions
        ):
            if not goals:
                goals = self._fallback_goals(state)
            state.extracted_goals = goals
            state.ready_for_products = True
        return state

    def _system_prompt(self, context: Optional[str]) -> str:
        """Build the system prompt with optional context."""
        if not context:
            return VALUES_CLARIFICATION_PROMPT
        return f"{VALUES_CLARIFICATION_PROMPT}\n\nSession context:\n{context}"

    def _has_summary(self, agent_response: str) -> bool:
        """Check if the agent response contains a summary."""
        lowered = agent_response.lower()
        summary_phrases = [
            "does that capture",
            "does that sound",
            "is that accurate",
            "is this accurate",
            "let me confirm",
            "to confirm",
            "here's what i'm hearing",
            "here is what i'm hearing",
            "recap",
            "summary",
        ]
        if any(phrase in lowered for phrase in summary_phrases):
            return True
        # Treat numbered/bulleted lists as summary cues.
        list_lines = [
            line
            for line in agent_response.splitlines()
            if line.strip().startswith(("-", "*")) or line.strip()[:2].isdigit()
        ]
        return len(list_lines) >= 2

    def _extract_goals(self, agent_response: str) -> List[str]:
        """Extract goals from the agent's summary response."""
        # Collect bullet/numbered list lines and labeled goals.
        goals: List[str] = []
        lines = agent_response.splitlines()
        for line in lines:
            raw = line.strip()
            if not raw:
                continue
            if raw.startswith(("-", "*")):
                candidate = raw.lstrip("-* ").strip()
                if candidate:
                    goals.append(candidate)
                continue
            if raw[0].isdigit() and "." in raw[:3]:
                candidate = raw.split(".", 1)[1].strip()
                if candidate:
                    goals.append(candidate)
                continue
            lowered = raw.lower()
            for prefix in ("goal:", "constraint:", "success:", "need:", "needs:"):
                if lowered.startswith(prefix):
                    goals.append(raw.split(":", 1)[1].strip())
                    break
        return goals or [agent_response.strip()]

    def _fallback_goals(self, state: GoalClarificationState) -> List[str]:
        """Fallback goals when summary parsing fails."""
        candidates: List[str] = []
        if state.query:
            candidates.append(state.query.strip())
        user_turns = [turn.content for turn in state.turns if turn.speaker == "user"]
        if user_turns:
            candidates.append(user_turns[-1].strip())
        return [candidate for candidate in candidates if candidate]


__all__ = ["GoalClarificationAgent"]
