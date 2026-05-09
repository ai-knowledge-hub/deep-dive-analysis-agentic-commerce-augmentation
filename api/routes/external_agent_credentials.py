from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from api.utils.principals import agent_principal_token_metadata

router = APIRouter(prefix="/external-agent/credentials", tags=["external-agent-credentials"])


class ExternalAgentCredentialMetadataResponse(BaseModel):
    token_type: str
    signing_algorithm: str
    current_key_id: str
    audience: str
    issuer: str
    default_ttl_seconds: int
    max_ttl_seconds: int
    rotation_supported: bool
    issuer_managed: bool
    issuance_endpoint: Optional[str] = None
    jwks_endpoint: Optional[str] = None


@router.get("/metadata")
def get_external_agent_credential_metadata() -> ExternalAgentCredentialMetadataResponse:
    return ExternalAgentCredentialMetadataResponse(**agent_principal_token_metadata())
