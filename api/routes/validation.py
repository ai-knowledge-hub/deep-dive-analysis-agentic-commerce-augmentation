from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.validation_service import ValidationService

router = APIRouter(prefix="/validation", tags=["validation"])


def _deps() -> AppDeps:
    return default_deps()


def _service(deps: AppDeps = Depends(_deps)) -> ValidationService:
    return ValidationService(deps=deps)


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


class ValidationProviderRunRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    callback_url: Optional[str] = None
    return_url: Optional[str] = None


class ValidationProviderCallbackRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    provider_run_id: Optional[str] = None
    callback_verified: bool = False
    callback_signature: Optional[str] = None
    structured_result: Dict[str, Any] = Field(default_factory=dict)
    raw_response: Optional[str] = None


@router.post("/jobs")
def create_job(
    payload: ValidationJobRequest, service: ValidationService = Depends(_service)
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    job = service.create_job(
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
    job_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    service: ValidationService = Depends(_service),
):
    scoped_client_id = require_client_id(client_id, user_id)
    try:
        result = service.run_job_scoped(job_id=job_id, client_id=scoped_client_id)
    except HTTPException:
        raise
    return result


@router.post("/jobs/{job_id}/external")
def submit_external(
    job_id: str,
    payload: ValidationExternalResultRequest,
    service: ValidationService = Depends(_service),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    result = service.submit_external_result(
        job_id=job_id,
        client_id=scoped_client_id,
        structured_result=payload.structured_result,
        raw_response=payload.raw_response,
        provider=payload.provider,
        model=payload.model,
    )
    return result


@router.post("/jobs/{job_id}/start-provider-run")
def start_provider_run(
    job_id: str,
    payload: ValidationProviderRunRequest,
    service: ValidationService = Depends(_service),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    return service.start_provider_run(
        job_id=job_id,
        client_id=scoped_client_id,
        callback_url=payload.callback_url,
        return_url=payload.return_url,
    )


@router.post("/jobs/{job_id}/provider-callback")
def submit_provider_callback(
    job_id: str,
    payload: ValidationProviderCallbackRequest,
    service: ValidationService = Depends(_service),
) -> Dict[str, Any]:
    if payload.client_id or payload.user_id:
        require_client_id(payload.client_id, payload.user_id)
    return service.submit_provider_result(
        job_id=job_id,
        structured_result=payload.structured_result,
        raw_response=payload.raw_response,
        provider=payload.provider,
        model=payload.model,
        provider_run_id=payload.provider_run_id,
        callback_verified=payload.callback_verified,
        callback_signature=payload.callback_signature,
    )


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    service: ValidationService = Depends(_service),
):
    scoped_client_id = require_client_id(client_id, user_id)
    return service.get_job(job_id=job_id, client_id=scoped_client_id)


@router.get("/jobs")
def list_jobs(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 50,
    service: ValidationService = Depends(_service),
):
    scoped_client_id = require_client_id(client_id, user_id)
    return service.list_jobs(
        client_id=scoped_client_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )


__all__ = ["router"]
