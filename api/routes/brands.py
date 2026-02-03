from __future__ import annotations

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from typing import Any, Dict, Optional

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.experiment_validation_service import (
    ExperimentValidationService,
)


if APIRouter:
    router = APIRouter(prefix="/brands", tags=["brands"])
    VALIDATIONS = ExperimentValidationService(deps=default_deps())

    @router.get("/{brand_id}")
    def get_brand(
        brand_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        client_scope = require_client_id(client_id, user_id)
        brand = default_deps().clients.get_brand(brand_id=brand_id)
        if not brand or brand.get("client_id") != client_scope:
            return {"error": "brand not found"}
        return {"brand": brand}

    @router.get("/{brand_id}/prediction-accuracy")
    def prediction_accuracy(
        brand_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        client_scope = require_client_id(client_id, user_id)
        summary = VALIDATIONS.brand_summary(brand_id=brand_id, client_id=client_scope)
        return {"summary": summary.to_dict()}
else:  # pragma: no cover
    router = None


__all__ = ["router"]
