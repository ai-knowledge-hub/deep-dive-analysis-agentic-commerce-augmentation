from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.ports.deps import AppDeps

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _deps() -> AppDeps:
    return default_deps()


class AnalyticsEventRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    variant_id: Optional[str] = None
    experiment_id: Optional[str] = None
    event_type: str = Field(..., min_length=1)
    source: Optional[str] = None
    event_timestamp: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
def create_event(payload: AnalyticsEventRequest) -> Dict[str, Any]:
    deps = _deps()
    client_id = require_client_id(payload.client_id, payload.user_id)
    event = deps.analytics_events.create_event(
        client_id=client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        experiment_id=payload.experiment_id,
        event_type=payload.event_type,
        source=payload.source,
        event_timestamp=payload.event_timestamp,
        metadata=payload.metadata,
    )
    return {"event": event}


__all__ = ["router"]
