from __future__ import annotations

from types import SimpleNamespace

try:
    from fastapi import APIRouter, Query
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None  # type: ignore

from infrastructure.llm.intent_classifier import build_intent_classifier
from application.services.intentionality_profiler import build_profile
from application.services.alignment_service import alignment_service
from pydantic import BaseModel, Field
from api.utils.tenancy import require_client_id

from infrastructure.commerce.search import search as search_products_fn


class HybridIntentClassifier:
    """Compatibility shim to keep API patch seams stable in tests."""

    def __init__(self) -> None:
        self._impl = build_intent_classifier()

    def classify(self, text: str, context: str | None = None):
        return self._impl.classify(text, context=context)


product_search = SimpleNamespace(search=search_products_fn)


def _search_products(query: str):
    return product_search.search(query)


if APIRouter:
    router = APIRouter(prefix="/products", tags=["products"])

    class ProfileRequest(BaseModel):
        product_id: str = Field(..., min_length=1)
        user_id: str | None = None
        client_id: str | None = None

    class AlignRequest(BaseModel):
        query: str = Field(..., min_length=1)
        product_ids: list[str] | None = None
        user_id: str | None = None
        client_id: str | None = None

    class EnrichRequest(BaseModel):
        product_id: str = Field(..., min_length=1)
        query: str | None = None
        user_id: str | None = None
        client_id: str | None = None

    @router.get("/search")
    def search_products(
        query: str = Query("", max_length=128),
        client_id: str | None = None,
        user_id: str | None = None,
    ):
        require_client_id(client_id, user_id)
        products = _search_products(query)
        return [product.__dict__ for product in products]

    @router.post("/profile")
    def profile_product(payload: ProfileRequest):
        """Return an intentionality profile for a single product."""
        require_client_id(payload.client_id, payload.user_id)
        product_id = payload.product_id
        products = _search_products(product_id)
        if not products:
            return {"error": "product not found"}
        return {"profile": build_profile(products[0]).to_dict()}

    @router.post("/align")
    def align_products(payload: AlignRequest):
        """Score a list of products against inferred intent."""
        require_client_id(payload.client_id, payload.user_id)
        query = payload.query
        product_ids = payload.product_ids or []
        classifier = HybridIntentClassifier()
        intent = classifier.classify(query).to_dict()
        goal_signals = _intent_goals(intent)
        candidates = []
        if product_ids:
            for pid in product_ids:
                candidates.extend(_search_products(pid))
        else:
            candidates = _search_products(query)
        alignment = alignment_service.assess(goal_signals, candidates)
        baseline = alignment_service.assess(
            goal_signals, candidates, use_semantic=False
        )
        per_product = [
            score.__dict__
            for score in alignment_service.score_products(goal_signals, candidates)
        ]
        alignment_payload = alignment.__dict__
        alignment_payload["baseline_score"] = baseline.score
        alignment_payload["per_product"] = per_product
        return {"intent": intent, "alignment": alignment_payload}

    @router.post("/enrich")
    def enrich_product(payload: EnrichRequest):
        """Return enriched product with intentionality profile and alignment."""
        require_client_id(payload.client_id, payload.user_id)
        product_id = payload.product_id
        query = payload.query or ""
        products = _search_products(product_id)
        if not products:
            return {"error": "product not found"}
        product = products[0]
        profile = build_profile(product).to_dict()
        alignment = None
        if query:
            classifier = HybridIntentClassifier()
            intent = classifier.classify(query).to_dict()
            goal_signals = _intent_goals(intent)
            alignment = alignment_service.assess(goal_signals, [product])
            baseline = alignment_service.assess(
                goal_signals, [product], use_semantic=False
            )
            alignment = alignment.__dict__
            alignment["baseline_score"] = baseline.score
            alignment["per_product"] = [
                score.__dict__
                for score in alignment_service.score_products(goal_signals, [product])
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
