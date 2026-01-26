from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from modules.simulation.domain import SimulationProduct
from modules.simulation.optimizer import optimize_product
from modules.simulation.runner import run_simulation
from modules.simulation import repository as simulation_repo


class SimulationService:
    def list_runs(
        self,
        *,
        client_id: str,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        runs = simulation_repo.list_runs(user_id=user_id, limit=limit, client_id=client_id)
        payload: list[Dict[str, Any]] = []
        for run in runs:
            payload.append(
                {
                    "id": run.get("id"),
                    "query": run.get("query"),
                    "created_at": run.get("created_at"),
                    "winner_id": (run.get("result") or {}).get("winner_id"),
                    "brand_id": run.get("brand_id"),
                    "product_id": run.get("product_id"),
                }
            )
        return {"runs": payload}

    def get_run(
        self, *, run_id: str, client_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        run_record = _get_run(run_id, user_id=user_id, client_id=client_id)
        return {"run": run_record}

    def list_lessons(
        self,
        *,
        client_id: str,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return {
            "lessons": simulation_repo.list_lessons(
                user_id=user_id, limit=limit, client_id=client_id
            )
        }

    def run(
        self,
        *,
        query: str,
        products: List[SimulationProduct],
        client_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        raw_products: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        result = run_simulation(query, products)
        tone_summary = (result.get("tone") or {}).get("summary")
        stored = simulation_repo.create_run(
            query=query,
            scenario={"query": query, "tone_suggestion": tone_summary},
            products=raw_products or [p.__dict__ for p in products],
            result=result,
            user_id=user_id,
            session_id=session_id,
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
        )
        return {"run_id": stored["id"], "result": result}

    def optimize(
        self,
        *,
        run_id: str,
        product_id: str,
        client_id: str,
        tone: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_record = _get_run(run_id, user_id=user_id, client_id=client_id)
        result = run_record.get("result") or {}
        gap_analysis = result.get("gap_analysis") or []
        target_gap = next(
            (gap for gap in gap_analysis if gap.get("product_id") == product_id),
            None,
        )
        if not target_gap:
            raise HTTPException(status_code=404, detail="Gap analysis not found")

        products = run_record.get("products") or []
        target = next((item for item in products if item.get("id") == product_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Product not found")

        optimized = optimize_product(
            _to_simulation_product(target),
            target_gap.get("missing_signals") or [],
            tone,
            (result.get("lessons") or []),
        )
        return {"run_id": run_id, "optimized": optimized, "gap": target_gap}

    def retest(
        self,
        *,
        run_id: str,
        optimized_products: List[SimulationProduct],
        client_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_record = _get_run(run_id, user_id=user_id, client_id=client_id)
        query = run_record.get("query") or run_record.get("scenario", {}).get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query missing for run")
        result = run_simulation(query, optimized_products)
        simulation_repo.update_retest(run_id, result)
        return {"run_id": run_id, "result": result}

    def update_tone(
        self,
        *,
        run_id: str,
        client_id: str,
        user_id: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_record = _get_run(run_id, user_id=user_id, client_id=client_id)
        scenario = run_record.get("scenario") or {}
        tone_clean = (tone or "").strip()
        scenario["confirmed_tone"] = tone_clean or None
        simulation_repo.update_scenario(run_id, scenario)
        return {"run_id": run_id, "tone": scenario.get("confirmed_tone")}

    def tone_from_brand(
        self,
        *,
        client_id: str,
        run_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if run_id:
            run_record = _get_run(run_id, user_id=user_id, client_id=client_id)
            scenario = run_record.get("scenario") or {}
            scenario["tone_source"] = "brand_site"
            simulation_repo.update_scenario(run_id, scenario)
        return {
            "status": "coming_soon",
            "message": "Brand tone import requires catalog integration.",
        }

    def attach(
        self,
        *,
        run_id: str,
        client_id: str,
        product_id: str,
        brand_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        _get_run(run_id, user_id=user_id, client_id=client_id)
        updated = simulation_repo.update_run_linkage(
            run_id,
            client_id=client_id,
            product_id=product_id,
            brand_id=brand_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Simulation run not found")
        return {
            "run_id": run_id,
            "product_id": updated.get("product_id"),
            "brand_id": updated.get("brand_id"),
        }


def _to_simulation_product(item: Dict[str, Any]) -> SimulationProduct:
    return SimulationProduct(
        id=item.get("id") or "",
        name=item.get("name") or "",
        description=item.get("description") or "",
        source=item.get("source") or "simulation",
        url=item.get("url"),
        price=item.get("price"),
        confidence=float(item.get("confidence") or 0.5),
        metadata=item.get("metadata") or {},
    )


def _get_run(run_id: str, *, user_id: Optional[str], client_id: str) -> Dict[str, Any]:
    run_record = simulation_repo.get_run(run_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    if run_record.get("client_id") and run_record.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    if user_id and run_record.get("user_id") and run_record.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return run_record

