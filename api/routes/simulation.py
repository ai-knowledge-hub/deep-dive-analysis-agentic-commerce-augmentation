from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore
    HTTPException = Exception  # type: ignore

from pydantic import BaseModel, Field

from modules.simulation.domain import SimulationProduct
from modules.simulation import repository as simulation_repo
from modules.simulation.runner import run_simulation
from modules.simulation.optimizer import optimize_product

if APIRouter:
    router = APIRouter(prefix="/simulation", tags=["simulation"])

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
        products: List[SimulationProductPayload]
        user_id: Optional[str] = None
        session_id: Optional[str] = None

    class SimulationOptimizeRequest(BaseModel):
        run_id: str
        product_id: str
        tone: Optional[str] = None
        user_id: Optional[str] = None

    class SimulationRetestRequest(BaseModel):
        run_id: str
        optimized_products: List[SimulationProductPayload]
        user_id: Optional[str] = None

    class SimulationToneRequest(BaseModel):
        run_id: str
        tone: Optional[str] = None
        user_id: Optional[str] = None

    class SimulationToneFromBrandRequest(BaseModel):
        run_id: Optional[str] = None
        user_id: Optional[str] = None

    @router.get("/runs")
    def list_runs(user_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        runs = simulation_repo.list_runs(user_id=user_id, limit=limit)
        payload = []
        for run in runs:
            payload.append(
                {
                    "id": run.get("id"),
                    "query": run.get("query"),
                    "created_at": run.get("created_at"),
                    "winner_id": (run.get("result") or {}).get("winner_id"),
                }
            )
        return {"runs": payload}

    @router.get("/runs/{run_id}")
    def get_run(run_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        run_record = _get_run(run_id, user_id)
        return {"run": run_record}

    @router.post("/run")
    def run(payload: SimulationRunRequest):
        products = [_to_simulation_product(item) for item in payload.products]
        result = run_simulation(payload.query, products)
        tone_summary = (result.get("tone") or {}).get("summary")
        stored = simulation_repo.create_run(
            query=payload.query,
            scenario={"query": payload.query, "tone_suggestion": tone_summary},
            products=[item.dict() for item in payload.products],
            result=result,
            user_id=payload.user_id,
            session_id=payload.session_id,
        )
        return {"run_id": stored["id"], "result": result}

    @router.post("/optimize")
    def optimize(payload: SimulationOptimizeRequest):
        run_record = _get_run(payload.run_id, payload.user_id)
        result = run_record.get("result") or {}
        gap_analysis = result.get("gap_analysis") or []
        target_gap = next(
            (
                gap
                for gap in gap_analysis
                if gap.get("product_id") == payload.product_id
            ),
            None,
        )
        if not target_gap:
            raise HTTPException(status_code=404, detail="Gap analysis not found")

        products = run_record.get("products") or []
        target = next(
            (item for item in products if item.get("id") == payload.product_id), None
        )
        if not target:
            raise HTTPException(status_code=404, detail="Product not found")

        optimized = optimize_product(
            _to_simulation_product(SimulationProductPayload(**target)),
            target_gap.get("missing_signals") or [],
            payload.tone,
        )
        return {"run_id": payload.run_id, "optimized": optimized, "gap": target_gap}

    @router.post("/retest")
    def retest(payload: SimulationRetestRequest):
        run_record = _get_run(payload.run_id, payload.user_id)
        query = run_record.get("query") or run_record.get("scenario", {}).get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query missing for run")

        products = [_to_simulation_product(item) for item in payload.optimized_products]
        result = run_simulation(query, products)
        simulation_repo.update_retest(payload.run_id, result)
        return {"run_id": payload.run_id, "result": result}

    @router.post("/tone")
    def update_tone(payload: SimulationToneRequest):
        run_record = _get_run(payload.run_id, payload.user_id)
        scenario = run_record.get("scenario") or {}
        tone = (payload.tone or "").strip()
        scenario["confirmed_tone"] = tone or None
        simulation_repo.update_scenario(payload.run_id, scenario)
        return {"run_id": payload.run_id, "tone": scenario.get("confirmed_tone")}

    @router.post("/tone/from-brand")
    def tone_from_brand(payload: SimulationToneFromBrandRequest):
        if payload.run_id:
            run_record = _get_run(payload.run_id, payload.user_id)
            scenario = run_record.get("scenario") or {}
            scenario["tone_source"] = "brand_site"
            simulation_repo.update_scenario(payload.run_id, scenario)
        return {
            "status": "coming_soon",
            "message": "Brand tone import requires catalog integration.",
        }
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


def _get_run(run_id: str, user_id: Optional[str]) -> Dict[str, Any]:
    run_record = simulation_repo.get_run(run_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    if user_id and run_record.get("user_id") and run_record.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return run_record
