"""Façade agent for intent detection."""

from __future__ import annotations

from llm.agents.intent_classifier import HybridIntentClassifier


class IntentAgent:
    def __init__(self) -> None:
        self._classifier = HybridIntentClassifier()

    def detect_intent(self, utterance: str) -> dict:
        return self._classifier.classify(utterance).to_dict()
