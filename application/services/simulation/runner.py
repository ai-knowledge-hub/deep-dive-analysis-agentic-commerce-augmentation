"""Application-layer simulation runner.

This is orchestration:
- infer intent from query
- compute alignment scores
- compute winner, gaps, lessons, tone
- generate intentionality profiles for display
"""

from __future__ import annotations

from typing import Dict, List

from application.ports.deps import AppDeps
from domain.commerce.types import Product
from domain.intent.goals import extract_intent_goals
from domain.simulation import ranking as domain_ranking
from application.services.evidence.alignment_service import AlignmentService
from application.services.evidence.intentionality_profiler import build_profile
from application.services.evidence.signal_extractor import SignalExtractor
from domain.simulation.types import SimulationProduct
from domain.simulation.tone import derive_tone


def run_simulation(
    *, deps: AppDeps, query: str, products: List[SimulationProduct]
) -> Dict[str, object]:
    intent = deps.classify_intent(query)
    goals = extract_intent_goals(intent, fallback=query)

    normalized = [_to_product(product) for product in products]
    alignment = AlignmentService(deps)
    scores_semantic = alignment.score_products(goals, normalized, use_semantic=True)
    scores_keyword = alignment.score_products(goals, normalized, use_semantic=False)

    score_map = {score.product_id: score for score in scores_semantic}

    ranked_scores = domain_ranking.rank_scores(
        [score.__dict__ for score in scores_semantic]
    )
    winner = domain_ranking.winner_id(ranked_scores)

    ranked_scores_keyword = domain_ranking.rank_scores(
        [score.__dict__ for score in scores_keyword]
    )
    winner_keyword = domain_ranking.winner_id(ranked_scores_keyword)

    gap_reports = []
    winner_product = None
    if winner:
        winner_product = next(
            (product for product in normalized if product.id == winner), None
        )

    primary_goal = goals[0] if goals else ""
    signal_extractor = SignalExtractor(deps)
    for product in normalized:
        score = score_map.get(product.id)
        if score:
            winner_for_comparison = (
                winner_product
                if winner_product and winner_product.id != product.id
                else None
            )
            gap = deps.simulation_analyze_gap(
                goal=primary_goal,
                product=product,
                score=score.score,
                winner=winner_for_comparison,
            )
            extracted = (
                signal_extractor.extract(
                    goal=primary_goal,
                    product={
                        "id": product.id,
                        "name": product.name,
                        "description": product.description,
                    },
                    winner={
                        "id": winner_for_comparison.id,
                        "name": winner_for_comparison.name,
                        "description": winner_for_comparison.description,
                    }
                    if winner_for_comparison
                    else None,
                )
                if winner_for_comparison
                else None
            )
            if extracted:
                if extracted.missing_signals:
                    gap["missing_signals"] = extracted.missing_signals[:5]
                    gap["summary"] = (
                        f"{gap['severity'].title()} gap: missing signals for "
                        f"{', '.join(extracted.missing_signals[:3])}."
                    )
                if extracted.winner_signals:
                    gap["winner_signals"] = extracted.winner_signals[:3]
                    gap["competitor_summary"] = (
                        f"Winner highlights {', '.join(extracted.winner_signals[:3])} "
                        f"for '{primary_goal}', while this product doesn't frame it that way."
                    )
            gap_reports.append(gap)

    tone = derive_tone(products)
    lessons = (
        deps.simulation_derive_lessons(primary_goal, gap_reports)
        if primary_goal
        else []
    )

    return {
        "intent": intent,
        "goals": goals,
        "scores": ranked_scores,
        "winner_id": winner,
        "scores_keyword": ranked_scores_keyword,
        "winner_id_keyword": winner_keyword,
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
