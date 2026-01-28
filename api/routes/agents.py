from __future__ import annotations

from typing import Optional

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.evidence_service import EvidenceService
from llm.agents.layer1_agent import Layer1Agent, Layer1RunConfig
from llm.agents.orchestrator_agent import OrchestratorAgent, OrchestratorConfig
from llm.agents.layer2_agent import Layer2Agent

if APIRouter:
    router = APIRouter(prefix="/agents", tags=["agents"])
    deps = default_deps()
    layer1_agent = Layer1Agent(evidence_service=EvidenceService(deps=deps))
    layer2_agent = Layer2Agent(deps=deps)
    orchestrator = OrchestratorAgent(layer1=layer1_agent, layer2=layer2_agent)

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
        return layer1_agent.run(
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
        return orchestrator.run(
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
        # Return both catalog candidates and protocol-layer candidates so we can
        # compare inference vs declaration paths.
        catalog = layer2_agent.get_catalog_candidates(
            client_id=client_scope, query=payload.query, limit=payload.limit
        )
        protocol = layer2_agent.discover_protocol_candidates(
            client_id=client_scope, query=payload.query, limit=payload.limit
        )
        return {"catalog": catalog, "protocol": protocol}
else:  # pragma: no cover
    router = None
