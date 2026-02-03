from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

try:
    from fastapi import APIRouter, Query
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None  # type: ignore

from infrastructure.llm.intent_classifier import build_intent_classifier
from application.services.intentionality_profiler import build_profile
from application.services.alignment_service import AlignmentService
from application.agents.layer2_agent import Layer2Agent
from application.services.simulation_service import _protocol_readiness_for_items
from pydantic import BaseModel, Field
from api.utils.tenancy import require_client_id
from api.composition import default_deps

from application.services.product_search import search_products_for_client


class HybridIntentClassifier:
    """Compatibility shim to keep API patch seams stable in tests."""

    def __init__(self) -> None:
        self._impl = build_intent_classifier()

    def classify(self, text: str, context: str | None = None):
        return self._impl.classify(text, context=context)


product_search = SimpleNamespace(search=search_products_for_client)
ALIGNMENT = AlignmentService(default_deps())


def _search_products(query: str, *, client_id: str, brand_id: str | None = None):
    return product_search.search(
        deps=default_deps(), query=query, client_id=client_id, brand_id=brand_id
    )


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

    class UpdateCopyRequest(BaseModel):
        product_id: str = Field(..., min_length=1)
        description: str = Field(..., min_length=1)
        source_url: str | None = None
        user_id: str | None = None
        client_id: str | None = None

    @router.get("/search")
    def search_products(
        query: str = Query("", max_length=128),
        client_id: str | None = None,
        user_id: str | None = None,
    ):
        require_client_id(client_id, user_id)
        products = _search_products(query, client_id=client_id)
        return [product.__dict__ for product in products]

    @router.get("/by-brand")
    def list_products_by_brand(
        brand_id: str = Query(..., min_length=1),
        client_id: str | None = None,
        user_id: str | None = None,
    ):
        require_client_id(client_id, user_id)
        products = default_deps().clients.list_products(brand_id=brand_id)
        return {"products": products}

    @router.post("/update-copy")
    def update_product_copy(payload: UpdateCopyRequest):
        require_client_id(payload.client_id, payload.user_id)
        deps = default_deps()
        product = deps.clients.get_product_for_client(
            client_id=payload.client_id, product_id=payload.product_id
        )
        if not product:
            return {"error": "product not found"}
        metadata = product.get("metadata") or {}
        creative = dict(metadata.get("creative") or {})
        creative["manual_copy"] = payload.description
        if payload.source_url:
            creative["source_url"] = payload.source_url
        creative["last_imported_at"] = creative.get("last_imported_at")
        metadata["creative"] = creative
        updated = deps.clients.update_product(
            product_id=payload.product_id,
            description=payload.description,
            metadata=metadata,
        )
        return {"product": updated}

    @router.post("/profile")
    def profile_product(payload: ProfileRequest):
        """Return an intentionality profile for a single product."""
        require_client_id(payload.client_id, payload.user_id)
        product_id = payload.product_id
        products = _search_products(product_id, client_id=payload.client_id)
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
                candidates.extend(_search_products(pid, client_id=payload.client_id))
        else:
            candidates = _search_products(query, client_id=payload.client_id)
        alignment = ALIGNMENT.assess(goal_signals, candidates)
        baseline = ALIGNMENT.assess(goal_signals, candidates, use_semantic=False)
        per_product = [
            score.__dict__
            for score in ALIGNMENT.score_products(goal_signals, candidates)
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
        products = _search_products(product_id, client_id=payload.client_id)
        if not products:
            return {"error": "product not found"}
        product = products[0]
        profile = build_profile(product).to_dict()
        alignment = None
        if query:
            classifier = HybridIntentClassifier()
            intent = classifier.classify(query).to_dict()
            goal_signals = _intent_goals(intent)
            alignment = ALIGNMENT.assess(goal_signals, [product])
            baseline = ALIGNMENT.assess(goal_signals, [product], use_semantic=False)
            alignment = alignment.__dict__
            alignment["baseline_score"] = baseline.score
            alignment["per_product"] = [
                score.__dict__
                for score in ALIGNMENT.score_products(goal_signals, [product])
            ]
        return {
            "product": product.__dict__,
            "profile": profile,
            "alignment": alignment,
        }

    @router.get("/{product_id}/schema-score")
    def schema_score(
        product_id: str,
        client_id: str | None = None,
        user_id: str | None = None,
    ) -> Dict[str, Any]:
        require_client_id(client_id, user_id)
        deps = default_deps()
        product = deps.clients.get_product_for_client(
            client_id=client_id, product_id=product_id
        )
        if not product:
            return {"error": "product not found"}
        flat = _flatten_product(product)
        agent = Layer2Agent()
        analysis = agent.analyze_products([flat])
        issues = analysis.get("schema_checks", [])[0].get("issues", [])
        score = _schema_score(issues)
        return {"score": score, "issues": issues, "summary": analysis.get("summary")}

    @router.get("/{product_id}/protocol-readiness")
    def protocol_readiness(
        product_id: str,
        client_id: str | None = None,
        user_id: str | None = None,
    ) -> Dict[str, Any]:
        require_client_id(client_id, user_id)
        deps = default_deps()
        product = deps.clients.get_product_for_client(
            client_id=client_id, product_id=product_id
        )
        if not product:
            return {"error": "product not found"}
        flat = _flatten_product(product)
        readiness = _protocol_readiness_for_items(deps, [flat])
        return {"readiness": readiness}

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

    def _flatten_product(product: dict) -> dict:
        metadata = product.get("metadata") or {}
        return {
            "id": product.get("id"),
            "name": product.get("name"),
            "description": product.get("description") or "",
            "source": metadata.get("source") or "product",
            "offer_url": metadata.get("offer_url") or metadata.get("url"),
            "merchant_name": metadata.get("merchant_name"),
            "price": metadata.get("price"),
            "availability": metadata.get("availability"),
            "metadata": metadata,
        }

    def _schema_score(issues: list[dict]) -> int:
        score = 100
        for issue in issues:
            severity = issue.get("severity")
            if severity == "error":
                score -= 25
            elif severity == "warning":
                score -= 10
        return max(0, min(score, 100))
else:  # pragma: no cover
    router = None
