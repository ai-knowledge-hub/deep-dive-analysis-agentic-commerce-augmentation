from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from pydantic import BaseModel, Field

from domain.simulation.types import SimulationProduct
from application.services.simulation_service import SimulationService
from api.utils.tenancy import require_client_id
from api.composition import default_deps

if APIRouter:
    router = APIRouter(prefix="/simulation", tags=["simulation"])
    simulation_service = SimulationService(deps=default_deps())

    class SimulationProductPayload(BaseModel):
        id: str
        name: str
        description: str
        source: str = "simulation"
        url: Optional[str] = None
        price: Optional[float] = None
        confidence: float = 0.5
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class SimulationRunRequest(BaseModel):
        query: str = Field(..., min_length=1)
        products: List[SimulationProductPayload] = Field(default_factory=list)
        auto_competitors: bool = True
        competitor_client_ids: Optional[List[str]] = None
        user_id: Optional[str] = None
        session_id: Optional[str] = None
        client_id: Optional[str] = None
        brand_id: Optional[str] = None
        product_id: Optional[str] = None

    class SimulationOptimizeRequest(BaseModel):
        run_id: str
        product_id: str
        tone: Optional[str] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        brand_id: Optional[str] = None

    class SimulationRetestRequest(BaseModel):
        run_id: str
        optimized_products: List[SimulationProductPayload]
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        brand_id: Optional[str] = None

    class SimulationToneRequest(BaseModel):
        run_id: str
        tone: Optional[str] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        brand_id: Optional[str] = None

    class SimulationToneFromBrandRequest(BaseModel):
        run_id: Optional[str] = None
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        brand_id: Optional[str] = None

    class SimulationAttachRequest(BaseModel):
        run_id: str
        product_id: str
        user_id: Optional[str] = None
        client_id: Optional[str] = None
        brand_id: Optional[str] = None

    @router.get("/runs")
    def list_runs(
        user_id: Optional[str] = None,
        limit: int = 20,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        client_scope = require_client_id(client_id, user_id)
        return simulation_service.list_runs(
            client_id=client_scope, user_id=user_id, limit=limit
        )

    @router.get("/runs/{run_id}")
    def get_run(
        run_id: str,
        user_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        client_scope = require_client_id(client_id, user_id)
        return simulation_service.get_run(
            run_id=run_id, client_id=client_scope, user_id=user_id
        )

    @router.get("/lessons")
    def list_lessons(
        user_id: Optional[str] = None,
        limit: int = 50,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        client_scope = require_client_id(client_id, user_id)
        return simulation_service.list_lessons(
            client_id=client_scope, user_id=user_id, limit=limit
        )

    @router.post("/run")
    def run(payload: SimulationRunRequest):
        products = [_to_simulation_product(item) for item in payload.products]
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return simulation_service.run(
            query=payload.query,
            products=products,
            client_id=client_scope,
            user_id=payload.user_id,
            session_id=payload.session_id,
            brand_id=payload.brand_id,
            product_id=payload.product_id,
            raw_products=[item.dict() for item in payload.products],
            auto_competitors=payload.auto_competitors,
            competitor_client_ids=payload.competitor_client_ids,
        )

    @router.post("/optimize")
    def optimize(payload: SimulationOptimizeRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return simulation_service.optimize(
            run_id=payload.run_id,
            product_id=payload.product_id,
            client_id=client_scope,
            tone=payload.tone,
            user_id=payload.user_id,
        )

    @router.post("/retest")
    def retest(payload: SimulationRetestRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        products = [_to_simulation_product(item) for item in payload.optimized_products]
        return simulation_service.retest(
            run_id=payload.run_id,
            optimized_products=products,
            client_id=client_scope,
            user_id=payload.user_id,
        )

    @router.post("/tone")
    def update_tone(payload: SimulationToneRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return simulation_service.update_tone(
            run_id=payload.run_id,
            client_id=client_scope,
            user_id=payload.user_id,
            tone=payload.tone,
        )

    @router.post("/tone/from-brand")
    def tone_from_brand(payload: SimulationToneFromBrandRequest):
        require_client_id(payload.client_id, payload.user_id)
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return simulation_service.tone_from_brand(
            client_id=client_scope,
            run_id=payload.run_id,
            user_id=payload.user_id,
        )

    @router.post("/attach")
    def attach(payload: SimulationAttachRequest):
        client_scope = require_client_id(payload.client_id, payload.user_id)
        return simulation_service.attach(
            run_id=payload.run_id,
            client_id=client_scope,
            product_id=payload.product_id,
            brand_id=payload.brand_id,
            user_id=payload.user_id,
        )
else:  # pragma: no cover
    router = None


def _to_simulation_product(item: "SimulationProductPayload") -> SimulationProduct:
    return SimulationProduct(
        id=item.id,
        name=item.name,
        description=item.description,
        source=item.source,
        url=item.url,
        price=item.price,
        confidence=item.confidence,
        metadata=item.metadata or {},
    )
