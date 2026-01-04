"""Façade agent for intent detection."""

from __future__ import annotations

from src.intent import classifier


class IntentAgent:
    def detect_intent(self, utterance: str) -> dict:
        intent = classifier.classify(utterance)
        return intent.to_dict()
