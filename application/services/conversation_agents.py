"""Conversation agents (application-layer orchestrators).

These are designed for dependency injection. `modules/conversation/agents.py`
wraps them for backward compatibility and test monkeypatch seams.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Protocol


class _Classifier(Protocol):
    def classify(self, text: str, context: str | None = None) -> Any: ...


class _PlanBuilder(Protocol):
    confidence_threshold: float
    fallback_limit: int

    def build_plan(self, **kwargs) -> dict: ...


class IntentAgent:
    """Façade agent for intent detection."""

    def __init__(
        self,
        *,
        classifier: _Classifier,
        context_for_fn: Callable[[Any], tuple[Any, str]],
        log_replay_fn: Callable[..., None] | None = None,
    ) -> None:
        self._classifier = classifier
        self._context_for = context_for_fn
        self._log_replay = log_replay_fn

    def detect_intent(self, utterance: str, manager: Any | None = None) -> dict:
        context: str | None = None
        if manager is not None:
            _, context = self._context_for(manager)
        result = self._classifier.classify(utterance, context=context).to_dict()
        if (
            self._log_replay
            and manager is not None
            and getattr(manager, "client_id", None)
        ):
            self._log_replay(
                query=utterance,
                result=result,
                context_used=bool(context),
                client_id=manager.client_id,
                user_id=getattr(manager, "user_id", None),
                session_id=getattr(manager, "session_id", None),
            )
        return result


class CommerceAgent:
    """Agent that orchestrates search and comparison within the commerce core."""

    def __init__(
        self,
        *,
        builder: _PlanBuilder,
        reason_fn: Callable[..., Any],
        assess_fn: Callable[..., Any],
        score_fn: Callable[..., Any],
        search_fn: Callable[[str, str | None, str | None], list],
    ) -> None:
        self._builder = builder
        self._reason_fn = reason_fn
        self._assess_fn = assess_fn
        self._score_fn = score_fn
        self._search_fn = search_fn

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
        client_id: str | None = None,
        brand_id: str | None = None,
    ) -> dict:
        return self._builder.build_plan(
            intent=intent,
            goals=goals,
            context=context,
            client_id=client_id,
            brand_id=brand_id,
            reason_fn=self._reason_fn,
            assess_fn=self._assess_fn,
            score_fn=self._score_fn,
        )

    def recommend(
        self, query: str, *, client_id: str | None = None, brand_id: str | None = None
    ) -> List[str]:
        return [product.name for product in self._search_fn(query, client_id, brand_id)]


class ExplainAgent:
    """Agent that provides short explanations of recommendations."""

    def explain(self, products: List[dict]) -> str:
        if not products:
            return "No protocol readiness results yet."
        explanations = []
        for product in products:
            base = (
                f"{product['name']} (confidence {product['confidence']:.2f}, "
                f"source {product['source']})"
            )
            if product["confidence"] < 0.75:
                base += " — verify details before purchasing."
            explanations.append(base)
        joined = "; ".join(explanations)
        return f"These items were selected based on intent alignment: {joined}"


class CapabilityAgent:
    """Maps semantic memory into capability statements."""

    def __init__(self, *, memory_factory: Callable[[], Any]) -> None:
        self._memory_factory = memory_factory

    def summarize(self) -> dict:
        memory = self._memory_factory()
        return {
            "goals": memory.get("goals"),
            "capabilities": memory.get("capabilities"),
        }


__all__ = ["IntentAgent", "CommerceAgent", "ExplainAgent", "CapabilityAgent"]
