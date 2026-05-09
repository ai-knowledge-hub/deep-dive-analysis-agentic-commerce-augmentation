from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentRunCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    experiment_id: Optional[str] = None
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None
    agent_profile_id: Optional[str] = None
    harness_id: Optional[str] = None
    policy_profile_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    objective: Dict[str, Any] = Field(default_factory=dict)
    allowed_capabilities: List[str] = Field(default_factory=list)
    capability_versions: Dict[str, Any] = Field(default_factory=dict)
    budgets: Dict[str, Any] = Field(default_factory=dict)
    approval_policy: Dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = True
    run_mode: Optional[str] = None
    state: str = "battery_ready"
    status: str = "planned"


class AgentRunListResponse(BaseModel):
    runs: List[Dict[str, Any]]


class AgentRunDetailResponse(BaseModel):
    run: Dict[str, Any]
    actions: List[Dict[str, Any]]


class AgentRunEventListResponse(BaseModel):
    events: List[Dict[str, Any]]
    page: Dict[str, Any]
