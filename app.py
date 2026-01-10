"""Entrypoint for running demo chat surfaces (CLI placeholder).

This file would normally wire Streamlit, Next.js, or Gemini surfaces into the
core platform. For now it just documents the flow so each layer can be mocked
independently during development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from config import env as _env  # noqa: F401  # ensure dotenv loaded for CLI runs
from modules.conversation.agents import IntentAgent, CommerceAgent, ReflectionAgent

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
        initial_goals = (
            [intent["label"].replace("_", " ")] if intent.get("label") else []
        )
        plan = commerce_agent.build_plan(intent, goals=initial_goals)
        print("Plan:", plan)
        reflection = reflection_agent.reflect(plan)
        print("Reflection:", reflection)


def main(surface: Surface = "hackathon") -> None:
    runtime = DemoRuntime(surface=surface)
    runtime.run()


if __name__ == "__main__":
    main()
