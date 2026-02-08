from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.services.validation_service import ValidationService

router = APIRouter(prefix="/validation", tags=["validation"])

SERVICE = ValidationService(deps=default_deps())


class ValidationJobRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    mode: str = Field(..., min_length=1)
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    input_payload: Dict[str, Any] = Field(default_factory=dict)


class ValidationExternalResultRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    structured_result: Dict[str, Any] = Field(default_factory=dict)
    raw_response: Optional[str] = None


@router.post("/jobs")
def create_job(payload: ValidationJobRequest) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    job = SERVICE.create_job(
        client_id=client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        provider=payload.provider,
        mode=payload.mode,
        model=payload.model,
        prompt_version=payload.prompt_version,
        input_payload=payload.input_payload,
        requested_by=payload.user_id,
    )
    return {"job": job}


@router.post("/jobs/{job_id}/run")
def run_job(
    job_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
):
    require_client_id(client_id, user_id)
    try:
        result = SERVICE.run_job(job_id=job_id)
    except HTTPException:
        raise
    return result


@router.post("/jobs/{job_id}/external")
def submit_external(
    job_id: str, payload: ValidationExternalResultRequest
) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    result = SERVICE.submit_external_result(
        job_id=job_id,
        structured_result=payload.structured_result,
        raw_response=payload.raw_response,
        provider=payload.provider,
        model=payload.model,
    )
    return result


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
):
    require_client_id(client_id, user_id)
    return SERVICE.get_job(job_id=job_id)


@router.get("/jobs")
def list_jobs(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 50,
):
    scoped_client_id = require_client_id(client_id, user_id)
    return SERVICE.list_jobs(
        client_id=scoped_client_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )


__all__ = ["router"]
