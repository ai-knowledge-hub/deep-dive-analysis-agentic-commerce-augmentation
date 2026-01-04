"""UI helper that surfaces semantic goals for transparency."""

from __future__ import annotations

from agents.capability_agent import CapabilityAgent


def render() -> dict:
    agent = CapabilityAgent()
    return agent.summarize()
