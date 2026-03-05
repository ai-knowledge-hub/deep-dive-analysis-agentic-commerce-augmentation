from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from domain.evidence.types import EvidenceProduct
from application.services.evidence.service import EvidenceService
from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.evidence.retriever import retrieve as _retrieve

if APIRouter:
    router = APIRouter(prefix="/evidence", tags=["evidence"])
    representation_router = APIRouter(prefix="/representation", tags=["evidence"])
    recommendation_router = APIRouter(prefix="/recommendation", tags=["evidence"])
    DEPS = default_deps()
    evidence_service = EvidenceService(deps=DEPS)

    def retrieve(query: str, max_items: int = 5):
        return _retrieve(query, max_items=max_items, run_research_fn=DEPS.run_research)

    class EvidenceAnalyzeRequest(BaseModel):
        query: str = Field(..., min_length=1)
        max_items: int = Field(default=5, ge=1, le=10)
        user_id: Optional[str] = None
        client_id: Optional[str] = None

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
        tone: Optional[str] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None

    class RecommendationVerifyRequest(BaseModel):
        query: str = Field(..., min_length=1)
        evidence_products: List[EvidenceItem]
        optimized: Optional[List[Dict[str, Any]]] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None

    class SignalProduct(BaseModel):
        id: Optional[str] = None
        name: Optional[str] = None
        description: Optional[str] = None

    class EvidenceSignalRequest(BaseModel):
        goal: str = Field(..., min_length=1)
        product: SignalProduct
        winner: Optional[SignalProduct] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None

    @router.post("/analyze")
    def analyze(payload: EvidenceAnalyzeRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return evidence_service.analyze(
            query=payload.query,
            max_items=payload.max_items,
            retrieve_fn=retrieve,
            client_id=client_scope,
            user_id=payload.user_id,
        )

    @representation_router.post("/optimize")
    def optimize_representation(payload: RepresentationOptimizeRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        evidence_products = [
            _evidence_from_payload(item) for item in payload.evidence_products
        ]
        return evidence_service.optimize_representation(
            evidence_products=evidence_products,
            query=payload.query,
            tone=payload.tone,
            client_id=client_scope,
            user_id=payload.user_id,
        )

    @recommendation_router.post("/verify")
    def verify_recommendations(payload: RecommendationVerifyRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        evidence_products = [
            _evidence_from_payload(item) for item in payload.evidence_products
        ]
        return evidence_service.verify_recommendations(
            query=payload.query,
            evidence_products=evidence_products,
            optimized=payload.optimized,
            client_id=client_scope,
            user_id=payload.user_id,
        )

    @router.post("/signals")
    def extract_signals(payload: EvidenceSignalRequest):
        require_client_id(payload.client_id, payload.user_id)
        winner_payload = payload.winner.model_dump() if payload.winner else None
        return {
            "signals": evidence_service.extract_signals(
                goal=payload.goal,
                product=payload.product.model_dump(),
                winner=winner_payload,
            )
        }
else:  # pragma: no cover
    router = None
    representation_router = None
    recommendation_router = None


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
