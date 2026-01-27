"""Compatibility shim for conversation agents.

Canonical implementations live in `application.services.conversation_agents` and
are dependency-injected. This module preserves monkeypatch seams used by tests:

- `modules.conversation.agents.HybridIntentClassifier`
- `modules.conversation.agents.reason_about_products`
- `modules.conversation.agents.SemanticMemory`
"""

from __future__ import annotations

from typing import List, Optional

from application.services.conversation_agents import (
    CapabilityAgent as _CapabilityAgent,
    CommerceAgent as _CommerceAgent,
    ExplainAgent as _ExplainAgent,
    IntentAgent as _IntentAgent,
)
from infrastructure.llm.intent_classifier import log_intent_replay
from modules.intent.llm_classifier import HybridIntentClassifier
from modules.conversation.context import context_for
from modules.memory.session_manager import SessionManager
from modules.memory.semantic import SemanticMemory
from modules.alignment import goal_alignment
from modules.alignment.llm_reasoner import reason_about_products
from modules.commerce.plan_builder import PlanBuilder
from modules.commerce import search as commerce_search


class IntentAgent:
    """Façade agent for intent detection."""

    def __init__(self) -> None:
        self._impl = _IntentAgent(
            classifier=HybridIntentClassifier(),
            context_for_fn=context_for,
            log_replay_fn=log_intent_replay,
        )

    def detect_intent(
        self, utterance: str, manager: SessionManager | None = None
    ) -> dict:
        return self._impl.detect_intent(utterance, manager=manager)


class CommerceAgent:
    """Agent that orchestrates search and comparison within the commerce core."""

    def __init__(self) -> None:
        self._impl = _CommerceAgent(
            builder=PlanBuilder(),
            reason_fn=reason_about_products,
            assess_fn=goal_alignment.assess,
            score_fn=goal_alignment.score_products,
            search_fn=commerce_search,
        )

    @property
    def confidence_threshold(self) -> float:
        return self._impl.confidence_threshold

    @property
    def fallback_limit(self) -> int:
        return self._impl.fallback_limit

    def build_plan(
        self,
        intent: dict,
        goals: Optional[List[str]] = None,
        context: str | None = None,
    ) -> dict:
        """Build a complete recommendation plan using LLM reasoning and goal alignment."""
        return self._impl.build_plan(intent, goals=goals, context=context)

    def recommend(self, query: str) -> List[str]:
        """Return product names matching the query."""
        return self._impl.recommend(query)


class ExplainAgent:
    """Agent that provides short explanations of recommendations."""

    def explain(self, products: List[dict]) -> str:
        return _ExplainAgent().explain(products)


class CapabilityAgent:
    """Maps semantic memory into capability statements."""

    def __init__(self) -> None:
        self._impl = _CapabilityAgent(memory_factory=SemanticMemory)

    def summarize(self) -> dict:
        return self._impl.summarize()


__all__ = [
    "IntentAgent",
    "CommerceAgent",
    "ExplainAgent",
    "CapabilityAgent",
]
