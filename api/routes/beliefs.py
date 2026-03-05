from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.ports.deps import AppDeps
from application.services.loop.belief_update_service import BeliefUpdateService
from application.services.experiment.brand_belief_service import BrandBeliefService


router = APIRouter(prefix="/beliefs", tags=["beliefs"])


def _deps() -> AppDeps:
    return default_deps()


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


class BeliefUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    hypothesis_key: str = Field(..., min_length=1)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    prior: Optional[float] = None
    likelihood: Optional[float] = None


@router.post("")
def create_belief(payload: BeliefCreateRequest) -> Dict[str, Any]:
    deps = _deps()
    service = BrandBeliefService(repo=deps.brand_beliefs)
    client_id = require_client_id(payload.client_id, payload.user_id)
    belief = service.create_belief(
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


@router.post("/update")
def update_belief(payload: BeliefUpdateRequest) -> Dict[str, Any]:
    deps = _deps()
    belief_update_service = BeliefUpdateService(deps=deps)
    client_id = require_client_id(payload.client_id, payload.user_id)
    revision = belief_update_service.update(
        client_id=client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        hypothesis_key=payload.hypothesis_key,
        evidence=payload.evidence,
        prior=payload.prior,
        likelihood=payload.likelihood,
    )
    return {"revision": revision}


@router.get("")
def list_beliefs(
    brand_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    deps = _deps()
    service = BrandBeliefService(repo=deps.brand_beliefs)
    scoped_client_id = require_client_id(client_id, user_id)
    beliefs = service.list_beliefs(
        client_id=scoped_client_id, brand_id=brand_id, limit=limit
    )
    return {"beliefs": beliefs}


@router.get("/latest")
def latest_belief(
    brand_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    deps = _deps()
    service = BrandBeliefService(repo=deps.brand_beliefs)
    scoped_client_id = require_client_id(client_id, user_id)
    belief = service.latest_belief(client_id=scoped_client_id, brand_id=brand_id)
    return {"belief": belief}


@router.get("/revisions")
def list_belief_revisions(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    hypothesis_key: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    deps = _deps()
    scoped_client_id = require_client_id(client_id, user_id)
    revisions = deps.belief_revisions.list_belief_revisions(
        client_id=scoped_client_id,
        brand_id=brand_id,
        product_id=product_id,
        hypothesis_key=hypothesis_key,
        limit=limit,
    )
    return {"revisions": revisions}
