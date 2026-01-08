"""Façade agent for intent detection."""

from __future__ import annotations

from llm.agents.intent_classifier import HybridIntentClassifier
from llm.orchestrator import build_context
from src.memory.session_manager import SessionManager


class IntentAgent:
    def __init__(self) -> None:
        self._classifier = HybridIntentClassifier()

    def detect_intent(self, utterance: str, manager: SessionManager | None = None) -> dict:
        context: str | None = None
        if manager is not None:
            _, context = build_context(manager)
        return self._classifier.classify(utterance, context=context).to_dict()
