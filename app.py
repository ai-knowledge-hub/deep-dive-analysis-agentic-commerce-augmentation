"""Entrypoint for running demo chat surfaces (CLI placeholder).

This file would normally wire Streamlit, Gradio, or Gemini surfaces into the
core platform. For now it just documents the flow so each layer can be mocked
independently during development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents.intent_agent import IntentAgent
from agents.commerce_agent import CommerceAgent
from agents.reflection_agent import ReflectionAgent

Surface = Literal["hackathon", "gpt", "gemini"]


@dataclass
class DemoRuntime:
    """High-level runtime that orchestrates the façade agents."""

    surface: Surface

    def run(self) -> None:
        print(f"Launching {self.surface} demo surface...")
        intent_agent = IntentAgent()
        commerce_agent = CommerceAgent()
        reflection_agent = ReflectionAgent()

        intent = intent_agent.detect_intent("Need a better workspace setup")
        print("Intent:", intent)
        plan = commerce_agent.build_plan(intent)
        print("Plan:", plan)
        reflection = reflection_agent.reflect(plan)
        print("Reflection:", reflection)


def main(surface: Surface = "hackathon") -> None:
    runtime = DemoRuntime(surface=surface)
    runtime.run()


if __name__ == "__main__":
    main()
