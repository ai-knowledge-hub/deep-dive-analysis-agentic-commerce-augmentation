"""Multi-turn values clarification agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from llm.gateway import chat
from llm.prompts import VALUES_CLARIFICATION_PROMPT


@dataclass
class ClarificationTurn:
    speaker: str
    content: str

    def to_dict(self) -> dict:
        return {"speaker": self.speaker, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict) -> "ClarificationTurn":
        return cls(speaker=data["speaker"], content=data["content"])


@dataclass
class ClarificationState:
    query: str
    turns: List[ClarificationTurn] = field(default_factory=list)
    extracted_goals: List[str] = field(default_factory=list)
    ready_for_products: bool = False
    metadata: dict = field(default_factory=dict)

    def add_turn(self, speaker: str, content: str) -> None:
        self.turns.append(ClarificationTurn(speaker=speaker, content=content))

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "turns": [turn.to_dict() for turn in self.turns],
            "extracted_goals": self.extracted_goals,
            "ready_for_products": self.ready_for_products,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClarificationState":
        turns = [ClarificationTurn.from_dict(item) for item in data.get("turns", [])]
        return cls(
            query=data["query"],
            turns=turns,
            extracted_goals=data.get("extracted_goals", []),
            ready_for_products=data.get("ready_for_products", False),
            metadata=data.get("metadata", {}),
        )


class ValuesAgent:
    """Guides the user through World B values clarification before commerce."""

    min_questions: int = 2

    def start(self, query: str, metadata: Optional[dict] = None) -> ClarificationState:
        state = ClarificationState(query=query, metadata=metadata or {})
        prompt = f"User request: {query}\nRespond per instructions."
        response = chat(
            messages=[
                {"role": "system", "content": VALUES_CLARIFICATION_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        state.add_turn("user", query)
        state.add_turn("agent", response.strip())
        return state

    def continue_dialogue(self, state: ClarificationState, user_message: str) -> ClarificationState:
        history = [
            {"role": turn.speaker, "content": turn.content}
            for turn in state.turns
        ]
        history.append({"role": "user", "content": user_message})
        response = chat(
            messages=[{"role": "system", "content": VALUES_CLARIFICATION_PROMPT}, *history]
        )
        state.add_turn("user", user_message)
        state.add_turn("agent", response.strip())
        if self._has_summary(response):
            state.extracted_goals = self._extract_goals(response)
            state.ready_for_products = True
        return state

    def _has_summary(self, agent_response: str) -> bool:
        return "does that capture" in agent_response.lower() or "summary" in agent_response.lower()

    def _extract_goals(self, agent_response: str) -> List[str]:
        # Simple heuristic: collect bullet/numbered list lines.
        goals: List[str] = []
        for line in agent_response.splitlines():
            stripped = line.strip("- ").strip()
            if stripped and any(keyword in stripped.lower() for keyword in ["goal", "reduce", "enable", "budget"]):
                goals.append(stripped)
        return goals or [agent_response.strip()]
