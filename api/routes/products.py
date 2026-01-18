from __future__ import annotations

try:
    from fastapi import APIRouter, Query
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None  # type: ignore

from modules.commerce import search as product_search
from modules.intent.llm_classifier import HybridIntentClassifier
from modules.intentionality.profiling import build_profile
from modules.alignment.goal_alignment import assess as assess_alignment
from modules.alignment.goal_alignment import score_products as score_alignment
from pydantic import BaseModel, Field

if APIRouter:
    router = APIRouter(prefix="/products", tags=["products"])

    class ProfileRequest(BaseModel):
        product_id: str = Field(..., min_length=1)

    class AlignRequest(BaseModel):
        query: str = Field(..., min_length=1)
        product_ids: list[str] | None = None

    class EnrichRequest(BaseModel):
        product_id: str = Field(..., min_length=1)
        query: str | None = None

    @router.get("/search")
    def search_products(query: str = Query("", max_length=128)):
        products = product_search.search(query)
        return [product.__dict__ for product in products]

    @router.post("/profile")
    def profile_product(payload: ProfileRequest):
        """Return an intentionality profile for a single product."""
        product_id = payload.product_id
        products = product_search.search(product_id)
        if not products:
            return {"error": "product not found"}
        return {"profile": build_profile(products[0]).to_dict()}

    @router.post("/align")
    def align_products(payload: AlignRequest):
        """Score a list of products against inferred intent."""
        query = payload.query
        product_ids = payload.product_ids or []
        classifier = HybridIntentClassifier()
        intent = classifier.classify(query).to_dict()
        goal_signals = _intent_goals(intent)
        candidates = []
        if product_ids:
            for pid in product_ids:
                candidates.extend(product_search.search(pid))
        else:
            candidates = product_search.search(query)
        alignment = assess_alignment(goal_signals, candidates)
        baseline = assess_alignment(
            goal_signals, candidates, use_semantic=False
        )
        per_product = [
            score.__dict__ for score in score_alignment(goal_signals, candidates)
        ]
        alignment_payload = alignment.__dict__
        alignment_payload["baseline_score"] = baseline.score
        alignment_payload["per_product"] = per_product
        return {"intent": intent, "alignment": alignment_payload}

    @router.post("/enrich")
    def enrich_product(payload: EnrichRequest):
        """Return enriched product with intentionality profile and alignment."""
        product_id = payload.product_id
        query = payload.query or ""
        products = product_search.search(product_id)
        if not products:
            return {"error": "product not found"}
        product = products[0]
        profile = build_profile(product).to_dict()
        alignment = None
        if query:
            classifier = HybridIntentClassifier()
            intent = classifier.classify(query).to_dict()
            goal_signals = _intent_goals(intent)
            alignment = assess_alignment(goal_signals, [product])
            baseline = assess_alignment(
                goal_signals, [product], use_semantic=False
            )
            alignment = alignment.__dict__
            alignment["baseline_score"] = baseline.score
            alignment["per_product"] = [
                score.__dict__
                for score in score_alignment(goal_signals, [product])
            ]
        return {
            "product": product.__dict__,
            "profile": profile,
            "alignment": alignment,
        }

    def _intent_goals(intent: dict) -> list[str]:
        goals: list[str] = []
        primary = intent.get("primary_goal") or intent.get("label")
        if primary and primary != "unknown":
            goals.append(primary)
        goals.extend(intent.get("secondary_goals") or [])
        goals.extend(intent.get("underlying_needs") or [])
        seen = set()
        deduped = []
        for goal in goals:
            if goal and goal != "unknown" and goal not in seen:
                seen.add(goal)
                deduped.append(goal)
        return deduped
else:  # pragma: no cover
    router = None
