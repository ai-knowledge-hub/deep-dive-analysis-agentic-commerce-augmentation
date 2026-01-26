from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from application.services.replay import default_versions
from llm.agents.harness.replay_logger import ReplayRecord, ToolCall
from llm.agents.harness.tool_executor import ToolExecutor, ToolSpec
from modules.memory.repositories import replays as replays_repo
from domain.simulation.ranking import lift_summary
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
        runs = simulation_repo.list_runs(
            user_id=user_id, limit=limit, client_id=client_id
        )
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
        executor = ToolExecutor()
        executor.register(
            ToolSpec(
                name="run_simulation",
                description="Infer intent, score products, compute gaps, derive lessons and tone.",
                func=lambda q, ps: run_simulation(q, ps),
            )
        )
        tool_calls: list[ToolCall] = []
        start = time.perf_counter()
        result = executor.execute("run_simulation", q=query, ps=products)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        tool_calls.append(
            ToolCall(
                name="run_simulation",
                arguments={"query": query, "products": [p.id for p in products]},
                result_summary=f"winner_id={(result or {}).get('winner_id')}",
                elapsed_ms=elapsed_ms,
            )
        )

        replay = ReplayRecord(
            run_type="simulation.run",
            inputs={"query": query, "product_ids": [p.id for p in products]},
            outputs={"winner_id": (result or {}).get("winner_id")},
            tool_calls=tool_calls,
            versions=default_versions(),
        )

        if isinstance(result, dict):
            result["_replay"] = replay.to_dict()

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
        replay_row = replays_repo.create_replay_record(
            run_type="simulation.run",
            record=replay.to_dict(),
            client_id=client_id,
            user_id=user_id,
            session_id=session_id,
            entity_type="simulation_run",
            entity_id=stored["id"],
        )
        if isinstance(result, dict):
            result["_replay_id"] = replay_row.get("id")
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
        replay = ReplayRecord(
            run_type="simulation.optimize",
            inputs={
                "run_id": run_id,
                "product_id": product_id,
                "tone": tone,
            },
            outputs={"optimized_product_id": (optimized or {}).get("id")},
            tool_calls=[
                ToolCall(
                    name="optimize_product",
                    arguments={"product_id": product_id},
                    result_summary="generated_optimized_copy",
                )
            ],
            versions=default_versions(scoring_version="n/a"),
        )
        return {
            "run_id": run_id,
            "optimized": optimized,
            "gap": target_gap,
            "replay": replay.to_dict(),
            "replay_id": replays_repo.create_replay_record(
                run_type="simulation.optimize",
                record=replay.to_dict(),
                client_id=client_id,
                user_id=user_id,
                session_id=run_record.get("session_id"),
                entity_type="simulation_run",
                entity_id=run_id,
            ).get("id"),
        }

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
        start = time.perf_counter()
        result = run_simulation(query, optimized_products)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Optional lift summary used by the UI (kept stable even if scores missing).
        before_scores = (run_record.get("result") or {}).get("scores") or []
        after_scores = (result or {}).get("scores") or []
        optimized_product_id = None
        if optimized_products:
            optimized_product_id = optimized_products[0].id
        if isinstance(result, dict):
            result["lift_summary"] = lift_summary(
                before_scores=before_scores,
                after_scores=after_scores,
                optimized_product_id=optimized_product_id,
            )

        replay = ReplayRecord(
            run_type="simulation.retest",
            inputs={
                "run_id": run_id,
                "query": query,
                "product_ids": [p.id for p in optimized_products],
            },
            outputs={"winner_id": (result or {}).get("winner_id")},
            tool_calls=[
                ToolCall(
                    name="run_simulation",
                    arguments={
                        "query": query,
                        "products": [p.id for p in optimized_products],
                    },
                    result_summary=f"winner_id={(result or {}).get('winner_id')}",
                    elapsed_ms=elapsed_ms,
                )
            ],
            versions=default_versions(),
        )
        if isinstance(result, dict):
            result["_replay"] = replay.to_dict()
            result["_replay_id"] = replays_repo.create_replay_record(
                run_type="simulation.retest",
                record=replay.to_dict(),
                client_id=client_id,
                user_id=user_id,
                session_id=run_record.get("session_id"),
                entity_type="simulation_run",
                entity_id=run_id,
            ).get("id")
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
