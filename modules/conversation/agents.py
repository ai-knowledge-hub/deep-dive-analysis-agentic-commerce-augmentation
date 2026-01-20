"""Conversation agents that orchestrate different aspects of dialogue."""

from __future__ import annotations

from typing import List, Optional

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
        self._classifier = HybridIntentClassifier()

    def detect_intent(
        self, utterance: str, manager: SessionManager | None = None
    ) -> dict:
        """Detect intent from utterance with optional session context."""
        context: str | None = None
        if manager is not None:
            _, context = context_for(manager)
        return self._classifier.classify(utterance, context=context).to_dict()


class CommerceAgent:
    """Agent that orchestrates search and comparison within the commerce core."""

    def __init__(self) -> None:
        self._builder = PlanBuilder()

    @property
    def confidence_threshold(self) -> float:
        return self._builder.confidence_threshold

    @property
    def fallback_limit(self) -> int:
        return self._builder.fallback_limit

    def build_plan(
        self,
        intent: dict,
        goals: Optional[List[str]] = None,
        context: str | None = None,
    ) -> dict:
        """Build a complete recommendation plan using LLM reasoning and goal alignment."""
        return self._builder.build_plan(
            intent=intent,
            goals=goals,
            context=context,
            reason_fn=reason_about_products,
            assess_fn=goal_alignment.assess,
            score_fn=goal_alignment.score_products,
        )

    def recommend(self, query: str) -> List[str]:
        """Return product names matching the query."""
        return [product.name for product in commerce_search(query)]


class ExplainAgent:
    """Agent that provides short explanations of recommendations."""

    def explain(self, products: List[dict]) -> str:
        """Explain product recommendations."""
        if not products:
            return "No catalog recommendations yet."
        explanations = []
        for product in products:
            base = f"{product['name']} (confidence {product['confidence']:.2f}, source {product['source']})"
            if product["confidence"] < 0.75:
                base += " — verify details before purchasing."
            explanations.append(base)
        joined = "; ".join(explanations)
        return f"These items were selected based on intent alignment: {joined}"


class CapabilityAgent:
    """Maps semantic memory into capability statements."""

    def summarize(self) -> dict:
        """Summarize capabilities from semantic memory."""
        memory = SemanticMemory()
        return {
            "goals": memory.get("goals"),
            "capabilities": memory.get("capabilities"),
        }


__all__ = [
    "IntentAgent",
    "CommerceAgent",
    "ExplainAgent",
    "CapabilityAgent",
]
