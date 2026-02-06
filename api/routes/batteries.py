from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.query_battery_service import QueryBatteryService
from application.services.query_battery_builder import QueryBatteryBuilder
from application.services.canonical_intent_spec_service import TOKEN_SYNONYMS, TYPO_MAP

router = APIRouter(prefix="/batteries", tags=["batteries"])

DEPS = default_deps()
SERVICE = QueryBatteryService(repo=DEPS.query_batteries)
BUILDER = QueryBatteryBuilder(
    batteries_repo=DEPS.query_batteries,
    clients_repo=DEPS.clients,
    generate_fn=DEPS.generate,
    beliefs_repo=DEPS.brand_beliefs,
    simulation_runs_repo=DEPS.simulation_runs,
    archetypes_repo=DEPS.audience_archetypes,
    analytics_events_repo=DEPS.analytics_events,
)


class BatteryCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    purpose: Optional[str] = None
    generation_mode: Optional[str] = None
    status: Optional[str] = None


class BatteryUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    name: Optional[str] = None
    purpose: Optional[str] = None
    generation_mode: Optional[str] = None
    status: Optional[str] = None


class BatteryQueryCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    query_text: str = Field(..., min_length=1)
    query_type: Optional[str] = None
    intent_archetype: Optional[str] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0.0)
    enabled: bool = True


class BatteryQueryUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    query_text: Optional[str] = None
    query_type: Optional[str] = None
    intent_archetype: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    weight: Optional[float] = Field(default=None, ge=0.0)
    enabled: Optional[bool] = None


class BatteryGenerateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    source: str = Field(..., min_length=1)
    seed_queries: Optional[list[str]] = None
    seed_features: Optional[list[str]] = None
    seed_use_cases: Optional[list[str]] = None
    limit: int = Field(default=15, ge=1, le=100)
    use_llm: Optional[bool] = False


@router.post("")
def create_battery(payload: BatteryCreateRequest) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    battery = SERVICE.create_battery(
        client_id=client_id,
        product_id=payload.product_id,
        brand_id=payload.brand_id,
        name=payload.name,
        purpose=payload.purpose,
        generation_mode=payload.generation_mode,
        status=payload.status or "draft",
    )
    return {"battery": battery}


@router.get("")
def list_batteries(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    product_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    batteries = SERVICE.list_batteries(
        client_id=scoped_client_id,
        product_id=product_id,
        brand_id=brand_id,
        status=status,
        limit=limit,
    )
    return {"batteries": batteries}


@router.get("/{battery_id}")
def get_battery(
    battery_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    battery = SERVICE.get_battery(battery_id=battery_id, client_id=scoped_client_id)
    return {"battery": battery}


@router.patch("/{battery_id}")
def update_battery(battery_id: str, payload: BatteryUpdateRequest) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    battery = SERVICE.update_battery(
        battery_id=battery_id,
        client_id=client_id,
        name=payload.name,
        purpose=payload.purpose,
        generation_mode=payload.generation_mode,
        status=payload.status,
    )
    return {"battery": battery}


@router.post("/{battery_id}/queries")
def add_query(battery_id: str, payload: BatteryQueryCreateRequest) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    query = SERVICE.add_query(
        battery_id=battery_id,
        query_text=payload.query_text,
        query_type=payload.query_type,
        intent_archetype=payload.intent_archetype,
        constraints=payload.constraints,
        weight=payload.weight,
        enabled=payload.enabled,
    )
    return {"query": query}


@router.get("/{battery_id}/queries")
def list_queries(
    battery_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    queries = SERVICE.list_queries(battery_id=battery_id)
    return {"queries": queries}


@router.patch("/{battery_id}/queries/{query_id}")
def update_query(
    battery_id: str, query_id: str, payload: BatteryQueryUpdateRequest
) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    query = SERVICE.update_query(
        query_id=query_id,
        query_text=payload.query_text,
        query_type=payload.query_type,
        intent_archetype=payload.intent_archetype,
        constraints=payload.constraints,
        weight=payload.weight,
        enabled=payload.enabled,
    )
    return {"query": query}


@router.delete("/{battery_id}/queries/{query_id}")
def delete_query(
    battery_id: str,
    query_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    deleted = SERVICE.delete_query(query_id=query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="query not found")
    return {"status": "deleted"}


@router.post("/{battery_id}/generate")
def generate_queries(
    battery_id: str, payload: BatteryGenerateRequest
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        created, report = BUILDER.generate_with_report(
            battery_id=battery_id,
            client_id=client_id,
            source=payload.source,
            seed_queries=payload.seed_queries,
            seed_features=payload.seed_features,
            seed_use_cases=payload.seed_use_cases,
            limit=payload.limit,
            use_llm=bool(payload.use_llm),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"queries": created, "report": report}


@router.get("/{battery_id}/metrics")
def get_metrics(
    battery_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    metrics = SERVICE.get_metrics(battery_id=battery_id)
    return {"metrics": metrics}


@router.get("/{battery_id}/eval-summary")
def get_eval_summary(
    battery_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    battery = SERVICE.get_battery(battery_id=battery_id, client_id=scoped_client_id)
    if not battery:
        raise HTTPException(status_code=404, detail="battery not found")

    events = DEPS.analytics_events.list_events(
        client_id=scoped_client_id,
        product_id=battery.get("product_id"),
        limit=500,
    )
    generation_events = [
        event
        for event in events
        if event.get("event_type") == "query_generation_eval"
        and (event.get("metadata") or {}).get("battery_id") == battery_id
    ]
    accepted_total = 0
    attempted_total = 0
    regeneration_events = 0
    clarification_events = 0
    for event in generation_events:
        report = (event.get("metadata") or {}).get("report") or {}
        accepted = int(report.get("accepted_count") or 0)
        rejected = int(report.get("rejected_count") or 0)
        accepted_total += accepted
        attempted_total += accepted + rejected
        if int(report.get("regeneration_count") or 0) > 0:
            regeneration_events += 1
        if bool(report.get("clarification_required")):
            clarification_events += 1
    acceptance_rate = (accepted_total / attempted_total) if attempted_total else 0.0
    regeneration_rate = (
        regeneration_events / len(generation_events) if generation_events else 0.0
    )
    clarification_rate = (
        clarification_events / len(generation_events) if generation_events else 0.0
    )

    experiments = DEPS.experiments.list_experiments(
        client_id=scoped_client_id,
        battery_id=battery_id,
        limit=200,
    )
    robust_win_rates: list[float] = []
    evidence_strength_breakdown: Dict[str, int] = {}
    for experiment in experiments:
        metrics = DEPS.experiment_runs.list_metrics(
            experiment_id=experiment.get("id"),
            limit=200,
        )
        for metric in metrics:
            payload = metric.get("metrics") or {}
            win_rate_robust = payload.get("win_rate_robust")
            if isinstance(win_rate_robust, (int, float)):
                robust_win_rates.append(float(win_rate_robust))
            evidence = payload.get("evidence_strength")
            if isinstance(evidence, str) and evidence.strip():
                evidence_strength_breakdown[evidence] = (
                    evidence_strength_breakdown.get(evidence, 0) + 1
                )

    validation_summary = DEPS.experiment_validations.accuracy_summary(
        client_id=scoped_client_id,
        brand_id=battery.get("brand_id"),
    )
    return {
        "summary": {
            "battery_id": battery_id,
            "generation_events": len(generation_events),
            "acceptance_rate": round(acceptance_rate, 4),
            "regeneration_rate": round(regeneration_rate, 4),
            "clarification_rate": round(clarification_rate, 4),
            "downstream_avg_win_rate_robust": round(
                sum(robust_win_rates) / len(robust_win_rates), 4
            )
            if robust_win_rates
            else None,
            "validation_accuracy": round(
                float(validation_summary.get("accuracy") or 0.0), 4
            ),
            "verified_runs": int(validation_summary.get("verified_runs") or 0),
            "evidence_strength_breakdown": evidence_strength_breakdown,
        }
    }


@router.get("/{battery_id}/ontology-updates")
def get_ontology_updates(
    battery_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    battery = SERVICE.get_battery(battery_id=battery_id, client_id=scoped_client_id)
    if not battery:
        raise HTTPException(status_code=404, detail="battery not found")
    events = DEPS.analytics_events.list_events(
        client_id=scoped_client_id,
        product_id=battery.get("product_id"),
        limit=500,
    )
    rejected_items: list[Dict[str, str]] = []
    for event in events:
        if event.get("event_type") != "query_generation_eval":
            continue
        metadata = event.get("metadata") or {}
        if metadata.get("battery_id") != battery_id:
            continue
        report = metadata.get("report") or {}
        rejected = report.get("rejected") or []
        for item in rejected:
            if isinstance(item, dict):
                text = str(item.get("query_text") or "").strip()
                reason = str(item.get("reason") or "").strip()
                if text and reason:
                    rejected_items.append({"query_text": text, "reason": reason})
    typo_hits: Dict[str, int] = {}
    synonym_candidates: Dict[str, int] = {}
    for item in rejected_items:
        tokens = re.findall(r"[a-zA-Z_]{3,}", item["query_text"].lower())
        for token in tokens:
            if token in TYPO_MAP:
                typo_hits[token] = typo_hits.get(token, 0) + 1
            if token in TOKEN_SYNONYMS:
                synonym_candidates[token] = synonym_candidates.get(token, 0) + 1
    typo_updates = [
        {"token": token, "suggested": TYPO_MAP[token], "count": count}
        for token, count in sorted(
            typo_hits.items(), key=lambda pair: pair[1], reverse=True
        )
    ]
    synonym_updates = [
        {"token": token, "suggested": TOKEN_SYNONYMS[token], "count": count}
        for token, count in sorted(
            synonym_candidates.items(), key=lambda pair: pair[1], reverse=True
        )
    ]
    return {
        "updates": {
            "battery_id": battery_id,
            "rejected_sample_count": len(rejected_items),
            "typo_updates": typo_updates[:20],
            "synonym_updates": synonym_updates[:20],
            "recommended_review_cadence": "weekly",
        }
    }


__all__ = ["router"]
