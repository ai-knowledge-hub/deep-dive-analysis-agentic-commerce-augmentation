from __future__ import annotations

from typing import Optional

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.evidence.service import EvidenceService
from application.agents.layer1_agent import Layer1Agent, Layer1RunConfig
from application.agents.orchestrator_agent import OrchestratorAgent, OrchestratorConfig
from application.agents.layer2_agent import Layer2Agent


def _deps():
    return default_deps()


def _layer1_agent() -> Layer1Agent:
    return Layer1Agent(evidence_service=EvidenceService(deps=_deps()))


def _layer2_agent() -> Layer2Agent:
    return Layer2Agent(deps=_deps())


def _orchestrator() -> OrchestratorAgent:
    return OrchestratorAgent(layer1=_layer1_agent(), layer2=_layer2_agent())


if APIRouter:
    router = APIRouter(prefix="/agents", tags=["agents"])

    class Layer1RunRequest(BaseModel):
        query: str = Field(..., min_length=1)
        max_items: int = Field(default=5, ge=1, le=10)
        optimize: bool = True
        verify: bool = True
        tone: Optional[str] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        session_id: Optional[str] = None

    @router.post("/layer1/run")
    def run_layer1(payload: Layer1RunRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return _layer1_agent().run(
            query=payload.query,
            tone=payload.tone,
            config=Layer1RunConfig(
                max_items=payload.max_items,
                optimize=payload.optimize,
                verify=payload.verify,
            ),
            client_id=client_scope,
            user_id=payload.user_id,
            session_id=payload.session_id,
        )

    class OrchestratorRunRequest(BaseModel):
        query: str = Field(..., min_length=1)
        products: Optional[list[dict]] = None
        run_layer2: bool = True
        max_items: int = Field(default=5, ge=1, le=10)
        optimize: bool = True
        verify: bool = True
        tone: Optional[str] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        session_id: Optional[str] = None

    @router.post("/query")
    def run_orchestrator(payload: OrchestratorRunRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return _orchestrator().run(
            query=payload.query,
            products=payload.products or None,
            tone=payload.tone,
            layer1_config=Layer1RunConfig(
                max_items=payload.max_items,
                optimize=payload.optimize,
                verify=payload.verify,
            ),
            config=OrchestratorConfig(run_layer2=payload.run_layer2),
            client_id=client_scope,
            user_id=payload.user_id,
            session_id=payload.session_id,
        )

    class Layer2CandidatesRequest(BaseModel):
        query: str = Field(..., min_length=1)
        client_id: Optional[str] = None
        limit: int = Field(default=8, ge=1, le=25)
        user_id: Optional[str] = None

    @router.post("/layer2/candidates")
    def layer2_candidates(payload: Layer2CandidatesRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        protocol = _layer2_agent().discover_protocol_candidates(
            client_id=client_scope, query=payload.query, limit=payload.limit
        )
        return {"protocol": protocol}
else:  # pragma: no cover
    router = None
