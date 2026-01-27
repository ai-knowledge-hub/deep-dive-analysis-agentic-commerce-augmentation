"""Application-layer simulation runner.

This is orchestration:
- infer intent from query
- compute alignment scores
- compute winner, gaps, lessons, tone
- generate intentionality profiles for display
"""

from __future__ import annotations

from typing import Dict, List

from domain.intent.goals import extract_intent_goals
from domain.simulation import ranking as domain_ranking
from infrastructure.llm.intent_classifier import classify_intent
from modules.alignment.goal_alignment import score_products
from modules.commerce.domain import Product
from application.services.intentionality_profiler import build_profile
from modules.simulation.domain import SimulationProduct
from modules.simulation.gap_analysis import analyze_gap, derive_lessons
from modules.simulation.tone import derive_tone


def run_simulation(query: str, products: List[SimulationProduct]) -> Dict[str, object]:
    intent = classify_intent(query)
    goals = extract_intent_goals(intent, fallback=query)

    normalized = [_to_product(product) for product in products]
    scores = score_products(goals, normalized)
    score_map = {score.product_id: score for score in scores}

    score_dicts = [score.__dict__ for score in scores]
    ranked_scores = domain_ranking.rank_scores(score_dicts)
    winner = domain_ranking.winner_id(ranked_scores)

    gap_reports = []
    winner_product = None
    if winner:
        winner_product = next((product for product in normalized if product.id == winner), None)

    primary_goal = goals[0] if goals else ""
    for product in normalized:
        score = score_map.get(product.id)
        if score:
            gap_reports.append(
                analyze_gap(
                    goal=primary_goal,
                    product=product,
                    score=score.score,
                    winner=winner_product,
                )
            )

    tone = derive_tone(products)
    lessons = derive_lessons(primary_goal, gap_reports) if primary_goal else []

    return {
        "intent": intent,
        "goals": goals,
        "scores": ranked_scores,
        "winner_id": winner,
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


__all__ = ["run_simulation"]
