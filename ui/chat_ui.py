"""Placeholder chat UI hooking into the façade agents."""

from __future__ import annotations

from agents.intent_agent import IntentAgent
from agents.commerce_agent import CommerceAgent


def render_demo(message: str) -> dict:
    intent_agent = IntentAgent()
    commerce_agent = CommerceAgent()
    intent = intent_agent.detect_intent(message)
    goals = [intent["label"].replace("_", " ")] if intent.get("label") else []
    plan = commerce_agent.build_plan(intent, goals=goals)
    return {"intent": intent, "plan": plan}
