"""Entrypoint for running demo chat surfaces (CLI placeholder).

This file would normally wire Streamlit, Next.js, or Gemini surfaces into the
core platform. For now it just documents the flow so each layer can be mocked
independently during development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from config import env as _env  # noqa: F401  # ensure dotenv loaded for CLI runs

Surface = Literal["hackathon", "gpt", "gemini"]


@dataclass
class DemoRuntime:
    """High-level runtime that orchestrates the façade agents."""

    surface: Surface

    def run(self) -> None:
        print(f"Launching {self.surface} demo surface...")
        from application.services.commerce_plan_builder import CommercePlanBuilder
        from application.services.alignment_service import alignment_service
        from application.services.intentionality_profiler import build_profile
        from infrastructure.commerce.search import search as catalog_search
        from infrastructure.commerce.compare import compare as catalog_compare
        from infrastructure.llm.intent_classifier import classify_intent
        from infrastructure.llm.product_reasoner import reason_about_products_default

        query = "Need a better workspace setup"
        intent = classify_intent(query)
        print("Intent:", intent)

        builder = CommercePlanBuilder(
            search_fn=lambda q: catalog_search(q),
            compare_fn=lambda products: catalog_compare(products),
            build_profile_fn=lambda product: build_profile(product),
        )
        plan = builder.build_plan(
            intent=intent,
            goals=[intent.get("primary_goal")] if intent.get("primary_goal") else [],
            reason_fn=reason_about_products_default,
            assess_fn=alignment_service.assess,
            score_fn=alignment_service.score_products,
        )
        print("Plan:", plan)


def main(surface: Surface = "hackathon") -> None:
    runtime = DemoRuntime(surface=surface)
    runtime.run()


if __name__ == "__main__":
    main()
