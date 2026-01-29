from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.query_battery_service import QueryBatteryService
from application.services.query_battery_builder import QueryBatteryBuilder

router = APIRouter(prefix="/batteries", tags=["batteries"])

DEPS = default_deps()
SERVICE = QueryBatteryService(repo=DEPS.query_batteries)
BUILDER = QueryBatteryBuilder(
    batteries_repo=DEPS.query_batteries,
    clients_repo=DEPS.clients,
    generate_fn=DEPS.generate,
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
    limit: int = Field(default=15, ge=1, le=100)


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
        created = BUILDER.generate(
            battery_id=battery_id,
            client_id=client_id,
            source=payload.source,
            seed_queries=payload.seed_queries,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"queries": created}


@router.get("/{battery_id}/metrics")
def get_metrics(
    battery_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    metrics = SERVICE.get_metrics(battery_id=battery_id)
    return {"metrics": metrics}


__all__ = ["router"]
