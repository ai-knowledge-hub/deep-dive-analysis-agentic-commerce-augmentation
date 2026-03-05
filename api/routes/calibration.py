from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps

router = APIRouter(prefix="/calibration", tags=["calibration"])


def _deps() -> AppDeps:
    return default_deps()


class CalibrationUpsertRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    provider: str = Field(..., min_length=1)
    metric_weights: Dict[str, Any] = Field(default_factory=dict)
    drift_score: float = Field(default=0.0, ge=0.0, le=1.0)


@router.get("/profile")
def get_profile(
    provider: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    brand_id: Optional[str] = None,
) -> Dict[str, Any]:
    deps = _deps()
    scoped_client_id = require_client_id(client_id, user_id)
    profile = deps.calibration_profiles.get_calibration_profile(
        client_id=scoped_client_id,
        brand_id=brand_id,
        provider=provider,
    )
    if not profile:
        profile = deps.calibration_profiles.get_calibration_profile(
            client_id=scoped_client_id,
            brand_id=None,
            provider=provider,
        )
    return {"profile": profile}


@router.post("/profile")
def upsert_profile(payload: CalibrationUpsertRequest) -> Dict[str, Any]:
    deps = _deps()
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    profile = deps.calibration_profiles.upsert_calibration_profile(
        client_id=scoped_client_id,
        brand_id=payload.brand_id,
        provider=payload.provider,
        metric_weights=payload.metric_weights,
        drift_score=payload.drift_score,
    )
    return {"profile": profile}


__all__ = ["router"]
