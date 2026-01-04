"""Placeholder chat UI hooking into the façade agents."""

from __future__ import annotations

from agents.intent_agent import IntentAgent
from agents.commerce_agent import CommerceAgent


def render_demo(message: str) -> dict:
    intent_agent = IntentAgent()
    commerce_agent = CommerceAgent()
    intent = intent_agent.detect_intent(message)
    plan = commerce_agent.build_plan(intent)
    return {"intent": intent, "plan": plan}
