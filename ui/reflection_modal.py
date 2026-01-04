"""UI fragment that shows empowerment reflections."""

from __future__ import annotations

from agents.reflection_agent import ReflectionAgent


def render(plan: dict) -> str:
    agent = ReflectionAgent()
    return agent.reflect(plan)
