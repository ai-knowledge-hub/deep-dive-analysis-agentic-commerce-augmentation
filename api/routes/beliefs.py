from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.brand_belief_service import BrandBeliefService


router = APIRouter(prefix="/beliefs", tags=["beliefs"])

DEPS = default_deps()
SERVICE = BrandBeliefService(repo=DEPS.brand_beliefs)


class BeliefCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: str = Field(..., min_length=1)
    product_id: Optional[str] = None
    hypothesis: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommendation: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("")
def create_belief(payload: BeliefCreateRequest) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    belief = SERVICE.create_belief(
        client_id=client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        hypothesis=payload.hypothesis,
        evidence=payload.evidence,
        recommendation=payload.recommendation,
        confidence=payload.confidence,
        metadata=payload.metadata,
    )
    return {"belief": belief}


@router.get("")
def list_beliefs(
    brand_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    beliefs = SERVICE.list_beliefs(
        client_id=scoped_client_id, brand_id=brand_id, limit=limit
    )
    return {"beliefs": beliefs}


@router.get("/latest")
def latest_belief(
    brand_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    belief = SERVICE.latest_belief(client_id=scoped_client_id, brand_id=brand_id)
    return {"belief": belief}
