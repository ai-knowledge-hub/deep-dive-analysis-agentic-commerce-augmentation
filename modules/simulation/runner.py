"""Simulation runner for the sandbox loop."""

from __future__ import annotations

from typing import Dict, List

from domain.simulation import ranking as domain_ranking
from modules.alignment.goal_alignment import score_products
from modules.commerce.domain import Product
from modules.intent.llm_classifier import HybridIntentClassifier
from modules.intentionality.profiling import build_profile
from modules.simulation.domain import SimulationProduct
from modules.simulation.gap_analysis import analyze_gap, derive_lessons
from modules.simulation.tone import derive_tone


def run_simulation(query: str, products: List[SimulationProduct]) -> Dict[str, object]:
    classifier = HybridIntentClassifier()
    intent = classifier.classify(query).to_dict()
    goals = _intent_goals(intent, fallback=query)

    normalized = [_to_product(product) for product in products]
    scores = score_products(goals, normalized)
    score_map = {score.product_id: score for score in scores}

    winner_id = domain_ranking.winner_id([score.__dict__ for score in scores])
    gap_reports = []
    winner_product = None
    if winner_id:
        winner_product = next(
            (product for product in normalized if product.id == winner_id),
            None,
        )
    for product in normalized:
        score = score_map.get(product.id)
        if score:
            gap_reports.append(
                analyze_gap(
                    goal=goals[0],
                    product=product,
                    score=score.score,
                    winner=winner_product,
                )
            )

    tone = derive_tone(products)

    lessons = derive_lessons(goals[0], gap_reports) if goals else []

    return {
        "intent": intent,
        "goals": goals,
        "scores": [score.__dict__ for score in scores],
        "winner_id": winner_id,
        "gap_analysis": gap_reports,
        "profiles": [build_profile(product).to_dict() for product in normalized],
        "lessons": lessons,
        "tone": tone,
    }


def _to_product(product: SimulationProduct) -> Product:
    return Product(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price or 0.0,
        tags=_tags_from_text(product.description or product.name),
        source=product.source,
        confidence=float(product.confidence or 0.5),
        metadata=product.metadata or {},
    )


def _tags_from_text(text: str) -> List[str]:
    tokens = [token for token in text.lower().split() if len(token) > 3]
    return list(dict.fromkeys(tokens))[:6]


def _intent_goals(intent: dict, fallback: str | None = None) -> List[str]:
    goals: List[str] = []
    primary = intent.get("primary_goal") or intent.get("label")
    if primary and primary != "unknown":
        goals.append(primary)
    goals.extend(intent.get("secondary_goals") or [])
    goals.extend(intent.get("underlying_needs") or [])
    deduped = list(dict.fromkeys([goal for goal in goals if goal]))
    if not deduped and fallback:
        deduped = [fallback]
    return deduped


__all__ = ["run_simulation"]
