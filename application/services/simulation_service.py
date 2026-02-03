from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from shared.replay.versions import default_versions
from shared.agents.replay_logger import ReplayLogger, ReplayRecord, ToolCall
from shared.agents.tool_executor import ToolExecutor, ToolSpec
from domain.simulation.ranking import lift_summary
from domain.simulation.types import SimulationProduct
from domain.protocol.types import ProtocolCandidate
from application.ports.deps import AppDeps
from application.services.simulation_optimizer import optimize_product
from application.services.simulation_runner import run_simulation


class SimulationService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def list_runs(
        self,
        *,
        client_id: str,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        runs = self._deps.simulation_runs.list_runs(
            user_id=user_id, limit=limit, client_id=client_id
        )
        payload: list[Dict[str, Any]] = []
        for run in runs:
            result = run.get("result") or {}
            winner_id = result.get("winner_id")
            payload.append(
                {
                    "id": run.get("id"),
                    "query": run.get("query"),
                    "created_at": run.get("created_at"),
                    "winner_id": winner_id,
                    "protocol_readiness_score": _extract_protocol_readiness_score(
                        result, winner_id
                    ),
                    "brand_id": run.get("brand_id"),
                    "product_id": run.get("product_id"),
                }
            )
        return {"runs": payload}

    def get_run(
        self, *, run_id: str, client_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        run_record = _get_run(self._deps, run_id, user_id=user_id, client_id=client_id)
        return {"run": run_record}

    def list_lessons(
        self,
        *,
        client_id: str,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return {
            "lessons": self._deps.simulation_runs.list_lessons(
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
        auto_competitors: bool = True,
        competitor_client_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        resolved_products = list(products or [])
        resolved_raw_products = list(
            raw_products or [p.__dict__ for p in resolved_products]
        )

        # "auto_competitors" means: include competitor products in addition to any
        # explicitly provided products (e.g., experiment variants). Previously we
        # only auto-added competitors when no products were provided, which made
        # experiments degenerate (the only candidate always wins).
        if auto_competitors:
            auto_products, auto_raw = self._auto_competitor_products(
                query=query,
                client_id=client_id,
                product_id=product_id,
                competitor_client_ids=competitor_client_ids,
            )
            resolved_products, resolved_raw_products = _merge_products(
                preferred_products=resolved_products,
                preferred_raw=resolved_raw_products,
                auto_products=auto_products,
                auto_raw=auto_raw,
            )

        executor = ToolExecutor()
        executor.register(
            ToolSpec(
                name="run_simulation",
                description="Infer intent, score products, compute gaps, derive lessons and tone.",
                func=lambda q, ps: run_simulation(
                    deps=self._deps, query=q, products=ps
                ),
            )
        )
        tool_calls: list[ToolCall] = []
        start = time.perf_counter()
        result = executor.execute("run_simulation", q=query, ps=resolved_products)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        tool_calls.append(
            ToolCall(
                name="run_simulation",
                arguments={
                    "query": query,
                    "products": [p.id for p in resolved_products],
                    "auto_competitors": auto_competitors,
                },
                result_summary=f"winner_id={(result or {}).get('winner_id')}",
                elapsed_ms=elapsed_ms,
            )
        )

        replay = ReplayRecord(
            run_type="simulation.run",
            inputs={"query": query, "product_ids": [p.id for p in resolved_products]},
            outputs={"winner_id": (result or {}).get("winner_id")},
            tool_calls=tool_calls,
            versions=default_versions(),
        )

        if isinstance(result, dict):
            result["_replay"] = replay.to_dict()

        if isinstance(result, dict):
            result["protocol_readiness"] = _protocol_readiness_for_items(
                self._deps, resolved_raw_products
            )

        tone_summary = (result.get("tone") or {}).get("summary")
        stored = self._deps.simulation_runs.create_run(
            query=query,
            scenario={"query": query, "tone_suggestion": tone_summary},
            products=resolved_raw_products,
            result=result,
            user_id=user_id,
            session_id=session_id,
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
        )
        logger = ReplayLogger(persist_fn=self._deps.replays.create_replay_record)
        replay_row = logger.persist(
            run_type="simulation.run",
            record=replay,
            client_id=client_id,
            user_id=user_id,
            session_id=session_id,
            entity_type="simulation_run",
            entity_id=stored["id"],
        )
        if isinstance(result, dict):
            result["_replay_id"] = replay_row.get("id")
        return {"run_id": stored["id"], "result": result}

    def _auto_competitor_products(
        self,
        *,
        query: str,
        client_id: str,
        product_id: Optional[str],
        competitor_client_ids: Optional[List[str]],
    ) -> tuple[List[SimulationProduct], List[Dict[str, Any]]]:
        # Base: include the selected product (if provided)
        raw: List[Dict[str, Any]] = []
        sim_products: List[SimulationProduct] = []

        if product_id:
            product = self._deps.clients.get_product_for_client(
                client_id=client_id, product_id=product_id
            )
            if product:
                # Best-effort enrich from metadata to match SimulationProductPayload fields
                metadata = product.get("metadata") or {}
                raw_item = {
                    "id": product["id"],
                    "brand_id": product.get("brand_id"),
                    "name": product["name"],
                    "description": product.get("description") or "",
                    "source": str(metadata.get("source") or "product"),
                    "url": metadata.get("offer_url") or metadata.get("url"),
                    "price": metadata.get("price"),
                    "confidence": 0.7,
                    "metadata": metadata,
                }
                raw.append(raw_item)
                sim_products.append(_to_simulation_product(raw_item))

        # Competitors: pick from other clients (or explicit list)
        if competitor_client_ids is None:
            competitor_client_ids = [
                c["id"]
                for c in self._deps.clients.list_clients()
                if c["id"] != client_id
            ][:3]

        for competitor_id in competitor_client_ids:
            if competitor_id == client_id:
                continue
            matches = self._deps.clients.search_products_for_client(
                client_id=competitor_id, query=query, limit=3
            )
            for match in matches:
                metadata = match.get("metadata") or {}
                raw_item = {
                    "id": match["id"],
                    "brand_id": match.get("brand_id"),
                    "name": match["name"],
                    "description": match.get("description") or "",
                    "source": str(metadata.get("source") or "product"),
                    "url": metadata.get("offer_url") or metadata.get("url"),
                    "price": metadata.get("price"),
                    "confidence": 0.65,
                    "metadata": metadata,
                }
                raw.append(raw_item)
                sim_products.append(_to_simulation_product(raw_item))

        # If no competitors matched, we still return the selected product (if any)
        return sim_products, raw

    def optimize(
        self,
        *,
        run_id: str,
        product_id: str,
        client_id: str,
        tone: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_record = _get_run(self._deps, run_id, user_id=user_id, client_id=client_id)
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
            generate_fn=self._deps.generate,
            build_optimization_prompt_fn=self._deps.build_optimization_prompt,
            tone=tone,
            lessons=(result.get("lessons") or []),
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
        logger = ReplayLogger(persist_fn=self._deps.replays.create_replay_record)
        return {
            "run_id": run_id,
            "optimized": optimized,
            "gap": target_gap,
            "replay": replay.to_dict(),
            "replay_id": logger.persist(
                run_type="simulation.optimize",
                record=replay,
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
        run_record = _get_run(self._deps, run_id, user_id=user_id, client_id=client_id)
        query = run_record.get("query") or run_record.get("scenario", {}).get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query missing for run")
        start = time.perf_counter()
        result = run_simulation(
            deps=self._deps, query=query, products=optimized_products
        )
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
            result["protocol_readiness"] = _protocol_readiness_for_items(
                self._deps,
                [_simulation_product_dict(p) for p in optimized_products],
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
            logger = ReplayLogger(persist_fn=self._deps.replays.create_replay_record)
            result["_replay_id"] = logger.persist(
                run_type="simulation.retest",
                record=replay,
                client_id=client_id,
                user_id=user_id,
                session_id=run_record.get("session_id"),
                entity_type="simulation_run",
                entity_id=run_id,
            ).get("id")
        self._deps.simulation_runs.update_retest(run_id, result)
        return {"run_id": run_id, "result": result}

    def update_tone(
        self,
        *,
        run_id: str,
        client_id: str,
        user_id: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_record = _get_run(self._deps, run_id, user_id=user_id, client_id=client_id)
        scenario = run_record.get("scenario") or {}
        tone_clean = (tone or "").strip()
        scenario["confirmed_tone"] = tone_clean or None
        self._deps.simulation_runs.update_scenario(run_id, scenario)
        return {"run_id": run_id, "tone": scenario.get("confirmed_tone")}

    def tone_from_brand(
        self,
        *,
        client_id: str,
        run_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_record = None
        scenario: Dict[str, Any] = {}
        if run_id:
            run_record = _get_run(
                self._deps, run_id, user_id=user_id, client_id=client_id
            )
            scenario = run_record.get("scenario") or {}

        brand_id = (run_record or {}).get("brand_id") or scenario.get("brand_id")
        product_id = (run_record or {}).get("product_id") or scenario.get("product_id")

        if not brand_id and product_id:
            product = self._deps.clients.get_product_for_client(
                client_id=client_id, product_id=product_id
            )
            brand_id = (product or {}).get("brand_id")

        if not brand_id:
            return {
                "status": "missing_brand",
                "message": "Select a brand (or attach a product) to derive brand tone.",
            }

        brand = self._deps.clients.get_brand(brand_id=brand_id)
        if not brand:
            return {
                "status": "missing_brand",
                "message": "Brand not found.",
            }

        brand_meta = brand.get("metadata") or {}
        product = None
        if product_id:
            product = self._deps.clients.get_product_for_client(
                client_id=client_id, product_id=product_id
            )

        sources: list[str] = []
        brand_copy = str(brand_meta.get("brand_copy") or "").strip()
        if brand_copy:
            sources.append(brand_copy)
        if product and product.get("description"):
            sources.append(str(product.get("description")))
        product_meta = (product or {}).get("metadata") or {}
        for key in ("product_copy", "description_source_text"):
            value = str(product_meta.get(key) or "").strip()
            if value:
                sources.append(value)

        if not sources:
            return {
                "status": "missing_copy",
                "message": "Add brand copy or a product description to derive tone.",
            }

        from shared.llm.prompts import build_brand_tone_prompt

        prompt = build_brand_tone_prompt(
            brand_name=brand.get("name") or "Brand", sources=sources
        )
        try:
            tone_summary = self._deps.generate(prompt).strip()
        except Exception:
            tone_summary = ""

        if not tone_summary:
            return {
                "status": "failed",
                "message": "Unable to derive brand tone from available copy.",
            }

        brand_meta = dict(brand_meta)
        brand_meta["tone_summary"] = tone_summary
        brand_meta["tone_source"] = "llm"
        brand_meta["tone_updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        self._deps.clients.update_brand_metadata(
            brand_id=brand_id,
            metadata=brand_meta,
        )

        if run_id:
            scenario["tone_source"] = "brand_profile"
            scenario["tone_suggestion"] = tone_summary
            scenario["brand_id"] = brand_id
            self._deps.simulation_runs.update_scenario(run_id, scenario)

        return {
            "status": "ok",
            "message": "Brand tone loaded from stored copy.",
            "tone": tone_summary,
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
        _get_run(self._deps, run_id, user_id=user_id, client_id=client_id)
        updated = self._deps.simulation_runs.update_run_linkage(
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
        brand_id=item.get("brand_id"),
        url=item.get("url"),
        price=item.get("price"),
        confidence=float(item.get("confidence") or 0.5),
        metadata=item.get("metadata") or {},
    )


def _simulation_product_dict(product: SimulationProduct) -> Dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "source": product.source,
        "brand_id": product.brand_id,
        "url": product.url,
        "price": product.price,
        "confidence": product.confidence,
        "metadata": product.metadata,
    }


def _merge_products(
    *,
    preferred_products: List[SimulationProduct],
    preferred_raw: List[Dict[str, Any]],
    auto_products: List[SimulationProduct],
    auto_raw: List[Dict[str, Any]],
) -> tuple[List[SimulationProduct], List[Dict[str, Any]]]:
    """Merge auto-discovered competitors with caller-provided products.

    Caller-provided products take precedence by product id (e.g., experiment
    variants override the baseline product record pulled from the DB).
    """
    merged_products: List[SimulationProduct] = []
    merged_raw: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(prod: SimulationProduct, raw_item: Dict[str, Any]) -> None:
        if not prod.id or prod.id in seen:
            return
        seen.add(prod.id)
        merged_products.append(prod)
        merged_raw.append(raw_item)

    for prod, raw_item in zip(preferred_products, preferred_raw):
        add(prod, raw_item)

    for prod, raw_item in zip(auto_products, auto_raw):
        add(prod, raw_item)

    return merged_products, merged_raw


def _protocol_readiness_for_items(
    deps: AppDeps, items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    readiness: List[Dict[str, Any]] = []
    for item in items:
        ucp_candidate = _to_protocol_candidate(item, protocol="ucp")
        ucp_issues = deps.protocol_validate_ucp(ucp_candidate)
        readiness.append(
            {
                "product_id": ucp_candidate.id,
                "protocol": ucp_candidate.protocol,
                "issues": [issue.__dict__ for issue in ucp_issues],
            }
        )
        acp_candidate = _to_protocol_candidate(item, protocol="acp")
        acp_issues = deps.protocol_validate_acp(acp_candidate)
        readiness.append(
            {
                "product_id": acp_candidate.id,
                "protocol": acp_candidate.protocol,
                "issues": [issue.__dict__ for issue in acp_issues],
            }
        )
    return readiness


def _to_protocol_candidate(item: Dict[str, Any], protocol: str) -> ProtocolCandidate:
    meta = item.get("metadata") or {}
    protocol_meta = meta.get(protocol) if isinstance(meta.get(protocol), dict) else {}
    attributes = protocol_meta.get("attributes") or meta.get("attributes") or {}
    return ProtocolCandidate(
        id=item.get("id") or "",
        name=item.get("name") or "",
        description=item.get("description") or "",
        protocol=protocol,  # type: ignore[arg-type]
        offer_url=_pick(protocol_meta, meta, "offer_url", "url") or item.get("url"),
        merchant_name=_pick(protocol_meta, meta, "merchant_name"),
        price=_pick_number(protocol_meta, meta, "price") or item.get("price"),
        currency=_pick(protocol_meta, meta, "currency"),
        availability=_pick(protocol_meta, meta, "availability"),
        available_for_sale=_pick_bool(protocol_meta, meta, "available_for_sale"),
        inventory_quantity=_pick_int(protocol_meta, meta, "inventory_quantity"),
        attributes=attributes if isinstance(attributes, dict) else {},
        raw={"product": {**item, "metadata": meta}},
    )


def _extract_protocol_readiness_score(
    result: Dict[str, Any], winner_id: Optional[str]
) -> Optional[int]:
    readiness = result.get("protocol_readiness") or []
    if not isinstance(readiness, list) or not readiness:
        return None
    for preferred_protocol in ("ucp", "acp"):
        entry = None
        if winner_id:
            entry = next(
                (
                    item
                    for item in readiness
                    if item.get("product_id") == winner_id
                    and item.get("protocol") == preferred_protocol
                ),
                None,
            )
        if entry is None:
            entry = next(
                (
                    item
                    for item in readiness
                    if item.get("protocol") == preferred_protocol
                ),
                None,
            )
        if not entry:
            continue
        issues = entry.get("issues") or []
        for issue in issues:
            if issue.get("field") in {"ucp_readiness_score", "acp_readiness_score"}:
                message = issue.get("message") or ""
                match = None
                if isinstance(message, str):
                    match = __import__("re").search(r"(\\d{1,3})\\s*/\\s*100", message)
                if match:
                    try:
                        return int(match.group(1))
                    except ValueError:
                        return None
    return None


def _pick(primary: Dict[str, Any], fallback: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in primary and primary.get(key) is not None:
            return primary.get(key)
        if key in fallback and fallback.get(key) is not None:
            return fallback.get(key)
    return None


def _pick_number(
    primary: Dict[str, Any], fallback: Dict[str, Any], key: str
) -> Optional[float]:
    value = _pick(primary, fallback, key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_int(
    primary: Dict[str, Any], fallback: Dict[str, Any], key: str
) -> Optional[int]:
    value = _pick(primary, fallback, key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick_bool(
    primary: Dict[str, Any], fallback: Dict[str, Any], key: str
) -> Optional[bool]:
    value = _pick(primary, fallback, key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _get_run(
    deps: AppDeps, run_id: str, *, user_id: Optional[str], client_id: str
) -> Dict[str, Any]:
    run_record = deps.simulation_runs.get_run(run_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    if run_record.get("client_id") and run_record.get("client_id") != client_id:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    if user_id and run_record.get("user_id") and run_record.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return run_record
