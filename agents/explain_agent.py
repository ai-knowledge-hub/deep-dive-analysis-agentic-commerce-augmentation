"""Agent that provides short explanations of recommendations."""

from __future__ import annotations

from typing import List


class ExplainAgent:
    def explain(self, recommendations: List[str]) -> str:
        joined = ", ".join(recommendations)
        return f"These items were selected because they reinforce autonomy: {joined}."
