from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.alignment import goal_alignment
from modules.evidence import EvidenceProduct, retrieve as default_retrieve, to_product, optimize
from modules.evidence.verify import average_alignment, simulate_actual
from modules.intent.llm_classifier import HybridIntentClassifier
from modules.intentionality.profiling import build_profile


class EvidenceService:
    def analyze(
        self,
        *,
        query: str,
        max_items: int = 5,
        retrieve_fn=default_retrieve,
    ) -> Dict[str, Any]:
        classifier = HybridIntentClassifier()
        intent = classifier.classify(query).to_dict()
        goals = _intent_goals(intent, fallback=query)

        evidence_products = retrieve_fn(query, max_items=max_items)
        products = [to_product(item) for item in evidence_products]
        profiles = [build_profile(product).to_dict() for product in products]
        alignment_scores = goal_alignment.score_products(goals, products)

        return {
            "intent": intent,
            "goals": goals,
            "evidence_products": [_evidence_to_dict(item) for item in evidence_products],
            "profiles": profiles,
            "alignment_scores": [score.__dict__ for score in alignment_scores],
        }

    def optimize_representation(
        self,
        *,
        evidence_products: List[EvidenceProduct],
        query: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> Dict[str, Any]:
        intent = None
        goals: List[str] = []
        if query:
            classifier = HybridIntentClassifier()
            intent = classifier.classify(query).to_dict()
            goals = _intent_goals(intent, fallback=query)

        optimized_pairs = optimize(evidence_products, goals=goals or None, tone=tone)

        before_products = [to_product(item) for item in evidence_products]
        after_products = [
            _product_with_description(product, pair["after"])
            for product, pair in zip(before_products, optimized_pairs)
        ]
        before_scores = goal_alignment.score_products(goals, before_products)
        after_scores = goal_alignment.score_products(goals, after_products)
        deltas = _score_deltas(before_scores, after_scores)

        return {
            "intent": intent,
            "goals": goals,
            "optimized": optimized_pairs,
            "alignment_deltas": deltas,
        }

    def verify_recommendations(
        self,
        *,
        query: str,
        evidence_products: List[EvidenceProduct],
        optimized: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        classifier = HybridIntentClassifier()
        intent = classifier.classify(query).to_dict()
        goals = _intent_goals(intent, fallback=query)

        before_products = [to_product(item) for item in evidence_products]
        before_scores = goal_alignment.score_products(goals, before_products)

        optimized_pairs = optimized or []
        after_products = before_products
        if optimized_pairs:
            after_products = [
                _product_with_description(product, pair.get("after") or product.description)
                for product, pair in zip(before_products, optimized_pairs)
            ]
        after_scores = goal_alignment.score_products(goals, after_products)

        predicted = _ranked_ids(after_scores)
        actual = simulate_actual(after_products)
        lift = average_alignment(after_scores) - average_alignment(before_scores)

        return {
            "intent": intent,
            "goals": goals,
            "predicted": predicted,
            "actual": actual,
            "lift": round(lift, 3),
            "baseline_alignment": [score.__dict__ for score in before_scores],
            "optimized_alignment": [score.__dict__ for score in after_scores],
        }


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


def _evidence_to_dict(item: EvidenceProduct) -> Dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "source": item.source,
        "url": item.url,
        "price": item.price,
        "confidence": item.confidence,
        "raw_text": item.raw_text,
        "metadata": item.metadata,
    }


def _product_with_description(product, description: str):
    return type(product)(**{**product.__dict__, "description": description})


def _score_deltas(before, after):
    before_map = {score.product_id: score.score for score in before}
    deltas = []
    for score in after:
        baseline = before_map.get(score.product_id, 0.0)
        deltas.append(
            {
                "product_id": score.product_id,
                "before": baseline,
                "after": score.score,
                "delta": round(score.score - baseline, 3),
            }
        )
    return deltas


def _ranked_ids(scores):
    ordered = sorted(scores, key=lambda s: s.score, reverse=True)
    return [score.product_id for score in ordered]
