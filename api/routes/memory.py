from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.loop.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


def _deps() -> AppDeps:
    return default_deps()


class MemoryDistillRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    vertical: Optional[str] = None
    artifact_type: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    quality_score: Optional[float] = None
    support_count: Optional[int] = None
    source: Optional[str] = None


@router.post("/distill")
def distill(payload: MemoryDistillRequest) -> Dict[str, Any]:
    deps = _deps()
    service = MemoryService(deps=deps)
    client_id = require_client_id(payload.client_id, payload.user_id)
    artifact = service.distill(
        client_id=client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        vertical=payload.vertical,
        artifact_type=payload.artifact_type,
        payload=payload.payload,
        quality_score=payload.quality_score,
        support_count=payload.support_count,
        source=payload.source,
    )
    return {"artifact": artifact}


@router.get("/artifacts")
def list_artifacts(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    artifact_type: str = "query_pattern",
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    vertical: Optional[str] = None,
    min_quality: float = 0.65,
    freshness_days: int = 180,
    limit: int = 20,
) -> Dict[str, Any]:
    deps = _deps()
    service = MemoryService(deps=deps)
    scoped_client_id = require_client_id(client_id, user_id)
    artifacts = service.retrieve(
        client_id=scoped_client_id,
        artifact_type=artifact_type,
        brand_id=brand_id,
        product_id=product_id,
        vertical=vertical,
        min_quality=min_quality,
        freshness_days=freshness_days,
        limit=limit,
    )
    return {"artifacts": artifacts}


__all__ = ["router"]
