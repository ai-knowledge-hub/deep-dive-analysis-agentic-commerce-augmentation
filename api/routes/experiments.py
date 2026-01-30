from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.services.experiment_service import ExperimentService
from application.services.experiment_runner import ExperimentRunner
from application.services.experiment_scheduler import ExperimentScheduler
from application.services.experiment_orchestrator import ExperimentOrchestrator

router = APIRouter(prefix="/experiments", tags=["experiments"])

DEPS = default_deps()
SERVICE = ExperimentService(repo=DEPS.experiments)
RUNNER = ExperimentRunner(deps=DEPS)
SCHEDULER = ExperimentScheduler(deps=DEPS)
ORCHESTRATOR = ExperimentOrchestrator(deps=DEPS)


class ExperimentCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: str = Field(..., min_length=1)
    battery_id: Optional[str] = None
    name: str = Field(..., min_length=1)
    hypothesis: Dict[str, Any] = Field(default_factory=dict)
    competitor_policy: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = None


class ExperimentUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    hypothesis: Optional[Dict[str, Any]] = None
    competitor_policy: Optional[Dict[str, Any]] = None


class VariantCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    label: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)


class ExperimentRunRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    variant_id: str = Field(..., min_length=1)


class ExperimentScheduleRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    enabled: bool
    interval_minutes: Optional[int] = Field(default=None, gt=0)


class ExperimentBackfillRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None


@router.post("")
def create_experiment(payload: ExperimentCreateRequest) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    experiment = SERVICE.create_experiment(
        client_id=client_id,
        product_id=payload.product_id,
        name=payload.name,
        battery_id=payload.battery_id,
        brand_id=payload.brand_id,
        hypothesis=payload.hypothesis,
        competitor_policy=payload.competitor_policy,
        status=payload.status or "draft",
    )
    return {"experiment": experiment}


@router.get("")
def list_experiments(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    product_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    battery_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    experiments = SERVICE.list_experiments(
        client_id=scoped_client_id,
        product_id=product_id,
        brand_id=brand_id,
        battery_id=battery_id,
        status=status,
        limit=limit,
    )
    return {"experiments": experiments}


@router.get("/{experiment_id}")
def get_experiment(
    experiment_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    experiment = SERVICE.get_experiment(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    return {"experiment": experiment}


@router.patch("/{experiment_id}")
def update_experiment(
    experiment_id: str, payload: ExperimentUpdateRequest
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    experiment = SERVICE.update_experiment(
        experiment_id=experiment_id,
        client_id=client_id,
        name=payload.name,
        status=payload.status,
        hypothesis=payload.hypothesis,
        competitor_policy=payload.competitor_policy,
    )
    return {"experiment": experiment}


@router.post("/{experiment_id}/variants")
def add_variant(experiment_id: str, payload: VariantCreateRequest) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    variant = SERVICE.add_variant(
        experiment_id=experiment_id,
        label=payload.label,
        variant_type=payload.type,
        payload=payload.payload,
    )
    return {"variant": variant}


@router.get("/{experiment_id}/variants")
def list_variants(
    experiment_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    variants = SERVICE.list_variants(experiment_id=experiment_id)
    return {"variants": variants}


@router.post("/{experiment_id}/run")
def run_experiment(experiment_id: str, payload: ExperimentRunRequest) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        result = RUNNER.run_experiment(
            experiment_id=experiment_id,
            variant_id=payload.variant_id,
            client_id=client_id,
            user_id=payload.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "experiment_id": result.experiment_id,
        "variant_id": result.variant_id,
        "runs": result.runs,
        "metrics": result.metrics,
    }


@router.post("/{experiment_id}/schedule")
def update_schedule(
    experiment_id: str, payload: ExperimentScheduleRequest
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        result = SCHEDULER.update_schedule(
            experiment_id=experiment_id,
            client_id=client_id,
            enabled=payload.enabled,
            interval_minutes=payload.interval_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"schedule": result.__dict__}


@router.post("/{experiment_id}/backfill")
def backfill_experiment(
    experiment_id: str, payload: ExperimentBackfillRequest
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        result = SCHEDULER.run_backfill(
            experiment_id=experiment_id,
            client_id=client_id,
            user_id=payload.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "experiment_id": result.experiment_id,
        "last_run_at": result.last_run_at,
        "next_run_at": result.next_run_at,
        "runs": [r.__dict__ for r in result.runs],
    }


@router.get("/{experiment_id}/next-test")
def next_test(
    experiment_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    recommendation = ORCHESTRATOR.suggest_next_test(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    DEPS.experiment_recommendations.create_recommendation(
        experiment_id=experiment_id,
        recommendation=recommendation.to_dict(),
    )
    return {"recommendation": recommendation.to_dict()}


@router.get("/{experiment_id}/runs")
def list_runs(
    experiment_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    runs = DEPS.experiment_runs.list_runs(
        experiment_id=experiment_id, variant_id=variant_id, limit=limit
    )
    return {"runs": runs}


@router.get("/{experiment_id}/metrics")
def list_metrics(
    experiment_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    metrics = DEPS.experiment_runs.list_metrics(
        experiment_id=experiment_id, variant_id=variant_id, limit=limit
    )
    return {"metrics": metrics}


@router.get("/{experiment_id}/recommendations")
def list_recommendations(
    experiment_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    require_client_id(client_id, user_id)
    recommendations = DEPS.experiment_recommendations.list_recommendations(
        experiment_id=experiment_id, limit=limit
    )
    return {"recommendations": recommendations}


__all__ = ["router"]
