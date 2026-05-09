from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExtensibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ExternalAgentJobCreateRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1)
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    experiment_id: Optional[str] = None
    objective: Dict[str, Any] = Field(default_factory=dict)
    skill_id: Optional[str] = None
    tool_id: Optional[str] = None
    capability_name: Optional[str] = None
    allowed_capabilities: List[str] = Field(default_factory=list)
    capability_versions: Dict[str, Any] = Field(default_factory=dict)
    budgets: Dict[str, Any] = Field(default_factory=dict)
    approval_policy: Dict[str, Any] = Field(default_factory=dict)
    harness_id: Optional[str] = None
    policy_profile_id: Optional[str] = None
    requires_approval: bool = True
    run_mode: str = "plan_only"
    plan_mode: Optional[str] = None
    state: str = "battery_ready"


class ExternalAgentJobPayload(ExtensibleModel):
    id: str
    client_id: Optional[str] = None
    principal_id: Optional[str] = None
    agent_profile_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    run_id: Optional[str] = None
    status: Optional[str] = None
    run_status: Optional[str] = None
    run_state: Optional[str] = None
    trace_id: Optional[str] = None
    requested_skill_id: Optional[str] = None
    requested_tool_id: Optional[str] = None
    receipt_id: Optional[str] = None
    receipt_type: Optional[str] = None
    receipt_signature_algorithm: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExternalAgentRunPayload(ExtensibleModel):
    id: str
    client_id: Optional[str] = None
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None
    agent_profile_id: Optional[str] = None
    status: Optional[str] = None
    state: Optional[str] = None
    trace_id: Optional[str] = None


class ExternalAgentJobResponse(BaseModel):
    job: ExternalAgentJobPayload
    run: ExternalAgentRunPayload
    idempotent_replay: bool = False


class ExternalAgentJobReceiptPayload(ExtensibleModel):
    receipt_id: Optional[str] = None
    receipt_type: Optional[str] = None
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    client_id: Optional[str] = None
    principal_id: Optional[str] = None
    status: Optional[str] = None
    trace_id: Optional[str] = None
    key_id: Optional[str] = None
    receipt_context_hash: Optional[str] = None
    signature: Optional[str] = None
    signature_algorithm: Optional[str] = None
    stale_context: Optional[bool] = None
    refresh_required_for_latest_context: Optional[bool] = None


class ExternalAgentJobReceiptResponse(BaseModel):
    receipt: ExternalAgentJobReceiptPayload


class ExternalAgentJobReceiptVerifyRequest(BaseModel):
    receipt: Dict[str, Any]


class ExternalAgentJobReceiptVerificationResponse(BaseModel):
    valid: bool
    valid_signature: bool
    valid_payload: bool
    valid_scope: bool
    key_id: Optional[str] = None
    signature_algorithm: Optional[str] = None
    receipt_payload: Dict[str, Any]
    blockers: List[str]


class ExternalAgentJobEventListResponse(BaseModel):
    events: List[Dict[str, Any]]
    page: Dict[str, Any]


class ExternalAgentJobReceiptListResponse(BaseModel):
    receipts: List[ExternalAgentJobReceiptPayload]


class ExternalAgentJobActivityItem(ExtensibleModel):
    type: str
    subtype: Optional[str] = None
    status: Optional[str] = None
    timestamp: Optional[str] = None
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    trace_id: Optional[str] = None


class ExternalAgentJobActivityResponse(BaseModel):
    job: ExternalAgentJobPayload
    summary: Dict[str, Any]
    items: List[ExternalAgentJobActivityItem]
    event_page: Dict[str, Any]
    page: Dict[str, Any]
