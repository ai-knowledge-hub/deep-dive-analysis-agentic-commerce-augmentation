from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.utils.tenancy import require_client_id
from api.composition import default_deps
from application.ports.deps import AppDeps
from application.services.experiment.service import ExperimentService
from application.services.experiment.runner import ExperimentRunner
from application.services.experiment.scheduler import ExperimentScheduler
from application.services.experiment.orchestrator import ExperimentOrchestrator
from application.services.experiment.variant_generator import ExperimentVariantGenerator
from application.services.experiment.validation_service import (
    ExperimentValidationService,
)
from application.services.experiment.execution_state_service import (
    ExperimentExecutionStateService,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _deps() -> AppDeps:
    return default_deps()


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
    hypothesis_id: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


class ExperimentRunRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    variant_id: str = Field(..., min_length=1)
    execution_mode: Literal["simulation", "retrieval_backed"] = "simulation"
    retrieval_max_results: int = Field(default=5, ge=1, le=10)


class ExperimentScheduleRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    enabled: bool
    interval_minutes: Optional[int] = Field(default=None, gt=0)


class ExperimentBackfillRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None


class ExperimentValidationRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    variant_id: Optional[str] = None
    platform: Optional[str] = None
    query_text: Optional[str] = None
    observed_products: list[str] = Field(default_factory=list)
    observed_winner_variant_id: Optional[str] = None
    observed_position: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class LoopVariantGenerateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    max_candidates: int = Field(default=3, ge=1, le=5)
    mode: Literal["loop_evidence", "cold_start"] = "loop_evidence"
    strategy: Literal["bottom_up", "top_down", "both"] = "both"


@router.post("")
def create_experiment(payload: ExperimentCreateRequest) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    client_id = require_client_id(payload.client_id, payload.user_id)
    experiment = service.create_experiment(
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
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(client_id, user_id)
    experiments = service.list_experiments(
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
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(client_id, user_id)
    experiment = service.get_experiment(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"experiment": experiment}


@router.patch("/{experiment_id}")
def update_experiment(
    experiment_id: str, payload: ExperimentUpdateRequest
) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    client_id = require_client_id(payload.client_id, payload.user_id)
    experiment = service.update_experiment(
        experiment_id=experiment_id,
        client_id=client_id,
        name=payload.name,
        status=payload.status,
        hypothesis=payload.hypothesis,
        competitor_policy=payload.competitor_policy,
    )
    return {"experiment": experiment}


@router.delete("/{experiment_id}")
def delete_experiment(
    experiment_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(client_id, user_id)
    deleted = service.delete_experiment(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"deleted": True, "experiment_id": experiment_id}


@router.post("/{experiment_id}/variants")
def add_variant(experiment_id: str, payload: VariantCreateRequest) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    experiment = service.get_experiment(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    inferred_hypothesis_id = payload.hypothesis_id
    if not inferred_hypothesis_id and isinstance(payload.payload, dict):
        inferred_hypothesis_id = str(payload.payload.get("hypothesis_id") or "") or None
    variant = service.add_variant(
        experiment_id=experiment_id,
        client_id=scoped_client_id,
        label=payload.label,
        variant_type=payload.type,
        payload=payload.payload,
        hypothesis_id=inferred_hypothesis_id,
        provenance=payload.provenance,
    )
    try:
        candidate_description = ""
        if isinstance(payload.payload, dict):
            candidate_description = str(
                payload.payload.get("description") or ""
            ).strip()
        if experiment and candidate_description:
            product = deps.clients.get_product_for_client(
                client_id=experiment["client_id"], product_id=experiment["product_id"]
            )
            base_description = str(
                (product or {}).get("description")
                or (product or {}).get("name")
                or "base copy"
            ).strip()
            if base_description and candidate_description != base_description:
                deps.copy_revisions.create_revision(
                    client_id=experiment["client_id"],
                    brand_id=experiment.get("brand_id"),
                    product_id=experiment["product_id"],
                    source_type="experiment",
                    source_id=experiment_id,
                    source_variant_id=variant.get("id"),
                    base_description=base_description,
                    candidate_description=candidate_description,
                    notes=f"Auto-created from experiment variant {variant.get('label')}.",
                    metadata={
                        "variant_label": variant.get("label"),
                        "variant_type": variant.get("type"),
                    },
                    created_by=payload.user_id,
                )
    except Exception:
        # Non-blocking: variant creation should not fail if revision persistence fails.
        pass
    return {"variant": variant}


@router.get("/{experiment_id}/variants")
def list_variants(
    experiment_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(client_id, user_id)
    experiment = service.get_experiment(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    variants = service.list_variants(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    return {"variants": variants}


@router.post("/{experiment_id}/run")
def run_experiment(experiment_id: str, payload: ExperimentRunRequest) -> Dict[str, Any]:
    deps = _deps()
    runner = ExperimentRunner(deps=deps)
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        result = runner.run_experiment(
            experiment_id=experiment_id,
            variant_id=payload.variant_id,
            client_id=client_id,
            user_id=payload.user_id,
            execution_mode=payload.execution_mode,
            retrieval_max_results=payload.retrieval_max_results,
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
    deps = _deps()
    scheduler = ExperimentScheduler(deps=deps)
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        result = scheduler.update_schedule(
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
    deps = _deps()
    scheduler = ExperimentScheduler(deps=deps)
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        result = scheduler.run_backfill(
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
    deps = _deps()
    orchestrator = ExperimentOrchestrator(deps=deps)
    scoped_client_id = require_client_id(client_id, user_id)
    recommendation = orchestrator.suggest_next_test(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    deps.experiment_recommendations.create_recommendation(
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
    deps = _deps()
    require_client_id(client_id, user_id)
    runs = deps.experiment_runs.list_runs(
        experiment_id=experiment_id, variant_id=variant_id, limit=limit
    )
    return {"runs": runs}


@router.get("/{experiment_id}/retrieval-snapshots")
def list_retrieval_snapshots(
    experiment_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    snapshot_version: Optional[int] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(client_id, user_id)
    experiment = service.get_experiment(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    rows = deps.experiment_retrieval_snapshots.list_snapshots(
        experiment_id=experiment_id,
        snapshot_version=snapshot_version,
        limit=limit,
    )
    return {"snapshots": rows}


@router.get("/{experiment_id}/hypotheses")
def list_hypotheses(
    experiment_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    snapshot_version: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(client_id, user_id)
    experiment = service.get_experiment(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    rows = deps.experiment_hypotheses.list_hypotheses(
        experiment_id=experiment_id,
        snapshot_version=snapshot_version,
        status=status,
        limit=limit,
    )
    return {"hypotheses": rows}


@router.delete("/{experiment_id}/runs/{run_id}")
def delete_run(
    experiment_id: str,
    run_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    deps = _deps()
    service = ExperimentService(repo=deps.experiments)
    scoped_client_id = require_client_id(client_id, user_id)
    run = deps.experiment_runs.get_run(run_id)
    if not run or run.get("experiment_id") != experiment_id:
        raise HTTPException(status_code=404, detail="Run not found")
    service.get_experiment(experiment_id=experiment_id, client_id=scoped_client_id)
    deleted = deps.experiment_runs.delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"deleted": True, "run_id": run_id}


@router.get("/{experiment_id}/metrics")
def list_metrics(
    experiment_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    deps = _deps()
    require_client_id(client_id, user_id)
    metrics = deps.experiment_runs.list_metrics(
        experiment_id=experiment_id, variant_id=variant_id, limit=limit
    )
    return {"metrics": metrics}


@router.post("/{experiment_id}/validations")
def log_validation(
    experiment_id: str, payload: ExperimentValidationRequest
) -> Dict[str, Any]:
    deps = _deps()
    validations = ExperimentValidationService(deps=deps)
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        validation = validations.log_validation(
            experiment_id=experiment_id,
            variant_id=payload.variant_id,
            client_id=client_id,
            platform=payload.platform,
            query_text=payload.query_text,
            observed_products=payload.observed_products,
            observed_winner_variant_id=payload.observed_winner_variant_id,
            observed_position=payload.observed_position,
            notes=payload.notes,
            created_at=payload.created_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = validations.experiment_summary(
        experiment_id=experiment_id, client_id=client_id
    )
    return {"validation": validation, "summary": summary.to_dict()}


@router.get("/{experiment_id}/validation-summary")
def validation_summary(
    experiment_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    deps = _deps()
    validations = ExperimentValidationService(deps=deps)
    scoped_client_id = require_client_id(client_id, user_id)
    summary = validations.experiment_summary(
        experiment_id=experiment_id, client_id=scoped_client_id
    )
    return {"summary": summary.to_dict()}


@router.get("/{experiment_id}/execution-state")
def execution_state(
    experiment_id: str, client_id: Optional[str] = None, user_id: Optional[str] = None
) -> Dict[str, Any]:
    deps = _deps()
    execution_state_service = ExperimentExecutionStateService(deps=deps)
    scoped_client_id = require_client_id(client_id, user_id)
    try:
        state = execution_state_service.get_state(
            experiment_id=experiment_id,
            client_id=scoped_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"state": state}


@router.get("/{experiment_id}/recommendations")
def list_recommendations(
    experiment_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    deps = _deps()
    require_client_id(client_id, user_id)
    recommendations = deps.experiment_recommendations.list_recommendations(
        experiment_id=experiment_id, limit=limit
    )
    return {"recommendations": recommendations}


@router.post("/{experiment_id}/variants/generate")
def generate_variant_from_loop_evidence(
    experiment_id: str,
    payload: LoopVariantGenerateRequest,
) -> Dict[str, Any]:
    deps = _deps()
    variant_generator = ExperimentVariantGenerator(deps=deps)
    client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        result = variant_generator.generate_variants(
            experiment_id=experiment_id,
            client_id=client_id,
            max_candidates=payload.max_candidates,
            user_id=payload.user_id,
            mode=payload.mode,
            strategy=payload.strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


__all__ = ["router"]
