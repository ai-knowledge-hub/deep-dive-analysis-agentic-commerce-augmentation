from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from modules.evidence import EvidenceProduct, retrieve, to_product, optimize
from modules.evidence.verify import simulate_actual, average_alignment
from modules.intent.llm_classifier import HybridIntentClassifier
from modules.intentionality.profiling import build_profile
from modules.alignment import goal_alignment

if APIRouter:
    router = APIRouter(prefix="/evidence", tags=["evidence"])
    representation_router = APIRouter(prefix="/representation", tags=["evidence"])
    recommendation_router = APIRouter(prefix="/recommendation", tags=["evidence"])

    class EvidenceAnalyzeRequest(BaseModel):
        query: str = Field(..., min_length=1)
        max_items: int = Field(default=5, ge=1, le=10)

    class EvidenceItem(BaseModel):
        id: str
        name: str
        description: str
        source: str
        url: Optional[str] = None
        price: Optional[float] = None
        confidence: float = 0.3
        raw_text: Optional[str] = None
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class RepresentationOptimizeRequest(BaseModel):
        query: Optional[str] = None
        evidence_products: List[EvidenceItem]

    class RecommendationVerifyRequest(BaseModel):
        query: str = Field(..., min_length=1)
        evidence_products: List[EvidenceItem]
        optimized: Optional[List[Dict[str, Any]]] = None

    @router.post("/analyze")
    def analyze(payload: EvidenceAnalyzeRequest):
        classifier = HybridIntentClassifier()
        intent = classifier.classify(payload.query).to_dict()
        goals = _intent_goals(intent)

        evidence_products = retrieve(payload.query, max_items=payload.max_items)
        products = [to_product(item) for item in evidence_products]
        profiles = [build_profile(product).to_dict() for product in products]
        alignment_scores = goal_alignment.score_products(goals, products)

        return {
            "intent": intent,
            "goals": goals,
            "evidence_products": [
                _evidence_to_dict(item) for item in evidence_products
            ],
            "profiles": profiles,
            "alignment_scores": [score.__dict__ for score in alignment_scores],
        }

    @representation_router.post("/optimize")
    def optimize_representation(payload: RepresentationOptimizeRequest):
        intent = None
        goals: List[str] = []
        if payload.query:
            classifier = HybridIntentClassifier()
            intent = classifier.classify(payload.query).to_dict()
            goals = _intent_goals(intent)

        evidence_products = [
            _evidence_from_payload(item) for item in payload.evidence_products
        ]
        optimized_pairs = optimize(evidence_products, goals=goals or None)

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

    @recommendation_router.post("/verify")
    def verify_recommendations(payload: RecommendationVerifyRequest):
        classifier = HybridIntentClassifier()
        intent = classifier.classify(payload.query).to_dict()
        goals = _intent_goals(intent)

        evidence_products = [
            _evidence_from_payload(item) for item in payload.evidence_products
        ]
        before_products = [to_product(item) for item in evidence_products]
        before_scores = goal_alignment.score_products(goals, before_products)

        optimized_pairs = payload.optimized or []
        after_products = before_products
        if optimized_pairs:
            after_products = [
                _product_with_description(
                    product, pair.get("after") or product.description
                )
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
else:  # pragma: no cover
    router = None
    representation_router = None
    recommendation_router = None


def _intent_goals(intent: dict) -> List[str]:
    goals: List[str] = []
    primary = intent.get("primary_goal") or intent.get("label")
    if primary and primary != "unknown":
        goals.append(primary)
    goals.extend(intent.get("secondary_goals") or [])
    goals.extend(intent.get("underlying_needs") or [])
    return list(dict.fromkeys([goal for goal in goals if goal]))


def _evidence_from_payload(item: "EvidenceItem") -> EvidenceProduct:
    return EvidenceProduct(
        id=item.id,
        name=item.name,
        description=item.description,
        source=item.source,
        url=item.url,
        price=item.price,
        confidence=item.confidence,
        raw_text=item.raw_text or "",
        metadata=item.metadata or {},
    )


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
