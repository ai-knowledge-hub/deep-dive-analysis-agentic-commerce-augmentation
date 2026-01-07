"""Agent that provides short explanations of recommendations."""

from __future__ import annotations

from typing import List


class ExplainAgent:
    def explain(self, products: List[dict]) -> str:
        explanations = []
        for product in products:
            base = f"{product['name']} (confidence {product['confidence']:.2f}, source {product['source']})"
            if product["confidence"] < 0.75:
                base += " — verify details before purchasing."
            explanations.append(base)
        joined = "; ".join(explanations)
        return f"These items were selected because they reinforce autonomy: {joined}"
