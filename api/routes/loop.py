from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.services.loop.policy_service import PolicyService
from application.services.loop.state_service import StateService
from infrastructure.db.connection import get_connection

router = APIRouter(prefix="/loop", tags=["loop"])

DEPS = default_deps()
STATE_SERVICE = StateService(deps=DEPS)
POLICY_SERVICE = PolicyService(deps=DEPS)


class LoopStepRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    provider: str = Field(..., min_length=1)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    expected_gain: float = Field(default=0.5, ge=0.0, le=1.0)


@router.get("/state")
def get_loop_state(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    state = STATE_SERVICE.latest(
        client_id=scoped_client_id, brand_id=brand_id, product_id=product_id
    )
    belief = DEPS.belief_revisions.get_latest_belief_revision(
        client_id=scoped_client_id,
        brand_id=brand_id,
        product_id=product_id,
    )
    decision = POLICY_SERVICE.latest_decision(
        client_id=scoped_client_id, brand_id=brand_id, product_id=product_id
    )
    return {
        "state": state,
        "latest_belief_revision": belief,
        "latest_decision": decision,
        "uncertainty": decision.get("uncertainty") if decision else None,
    }


@router.post("/step")
def loop_step(payload: LoopStepRequest) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    chosen = POLICY_SERVICE.choose_action(
        client_id=scoped_client_id,
        provider=payload.provider,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        uncertainty=payload.uncertainty,
        expected_gain=payload.expected_gain,
    )
    decision = POLICY_SERVICE.record_decision(
        client_id=scoped_client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        policy_action=str(chosen["action"]),
        uncertainty=payload.uncertainty,
        expected_gain=payload.expected_gain,
        selected_reason="loop_step",
    )
    return {
        "decision": decision,
        "recommended_action": chosen["action"],
        "action_score": chosen["score"],
    }


@router.get("/metrics")
def get_loop_metrics(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    range_days: int = 30,
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    lookback_days = max(1, min(365, int(range_days)))
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    revisions = DEPS.belief_revisions.list_belief_revisions(
        client_id=scoped_client_id,
        brand_id=brand_id,
        product_id=product_id,
        limit=500,
    )
    updates_in_range = [
        item for item in revisions if _parse_timestamp(item.get("created_at")) >= cutoff
    ]
    avg_confidence = (
        sum(float(item.get("confidence") or 0.0) for item in updates_in_range)
        / len(updates_in_range)
        if updates_in_range
        else 0.0
    )

    decisions = DEPS.decision_events.list_decision_events(
        client_id=scoped_client_id,
        brand_id=brand_id,
        product_id=product_id,
        limit=500,
    )
    decision_in_range = [
        item for item in decisions if _parse_timestamp(item.get("created_at")) >= cutoff
    ]
    action_distribution: Dict[str, int] = {}
    for item in decision_in_range:
        action = str(item.get("policy_action") or "unknown")
        action_distribution[action] = action_distribution.get(action, 0) + 1

    events = DEPS.analytics_events.list_events(
        client_id=scoped_client_id,
        brand_id=brand_id,
        product_id=product_id,
        limit=1000,
    )
    eval_events = []
    for event in events:
        if event.get("event_type") != "query_generation_eval":
            continue
        if _parse_timestamp(event.get("created_at")) < cutoff:
            continue
        eval_events.append(event)
    accepted_total = 0
    attempted_total = 0
    regeneration_events = 0
    for event in eval_events:
        report = (event.get("metadata") or {}).get("report") or {}
        accepted = int(report.get("accepted_count") or 0)
        rejected = int(report.get("rejected_count") or 0)
        accepted_total += accepted
        attempted_total += accepted + rejected
        if int(report.get("regeneration_count") or 0) > 0:
            regeneration_events += 1
    acceptance_rate = (accepted_total / attempted_total) if attempted_total else 0.0
    regeneration_rate = regeneration_events / len(eval_events) if eval_events else 0.0

    # Direct SQL is used here to pair synthetic vs observed outcomes by provider + entity.
    conn = get_connection()
    validation_filters = ["vj.client_id = ?", "vr.created_at >= ?"]
    validation_params: list[Any] = [
        scoped_client_id,
        cutoff.strftime("%Y-%m-%d %H:%M:%S"),
    ]
    if brand_id:
        validation_filters.append("vj.brand_id = ?")
        validation_params.append(brand_id)
    if product_id:
        validation_filters.append("vj.product_id = ?")
        validation_params.append(product_id)
    where_clause = " AND ".join(validation_filters)
    agreement_rows = conn.execute(
        f"""
        SELECT
            lower(vr.provider) AS provider,
            vj.entity_type AS entity_type,
            vj.entity_id AS entity_id,
            vj.mode AS mode,
            AVG(COALESCE(vr.score, 0.0)) AS avg_score
        FROM validation_results vr
        JOIN validation_jobs vj ON vj.id = vr.job_id
        WHERE {where_clause}
        GROUP BY lower(vr.provider), vj.entity_type, vj.entity_id, vj.mode
        """,
        validation_params,
    ).fetchall()
    agreement_map: Dict[tuple[str, str, str], Dict[str, float]] = {}
    for row in agreement_rows:
        provider = str(row["provider"] or "").strip().lower()
        entity_type = str(row["entity_type"] or "").strip()
        entity_id = str(row["entity_id"] or "").strip()
        if not provider or not entity_type or not entity_id:
            continue
        key = (provider, entity_type, entity_id)
        if key not in agreement_map:
            agreement_map[key] = {}
        mode = str(row["mode"] or "").strip().lower()
        if mode == "external":
            agreement_map[key]["observed"] = float(row["avg_score"] or 0.0)
        else:
            agreement_map[key]["synthetic"] = float(row["avg_score"] or 0.0)
    agreement_scores: list[float] = []
    for values in agreement_map.values():
        if "synthetic" in values and "observed" in values:
            agreement_scores.append(1.0 - abs(values["observed"] - values["synthetic"]))
    observed_vs_synthetic_agreement = (
        sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0.0
    )

    profiles = DEPS.calibration_profiles.list_calibration_profiles(
        client_id=scoped_client_id,
        brand_id=brand_id,
        limit=100,
    )
    drift_values = [float(profile.get("drift_score") or 0.0) for profile in profiles]
    drift_average = sum(drift_values) / len(drift_values) if drift_values else 0.0
    drift_max = max(drift_values) if drift_values else 0.0

    return {
        "range_days": lookback_days,
        "update_frequency": {
            "belief_updates": len(updates_in_range),
            "decision_events": len(decision_in_range),
            "avg_confidence": round(avg_confidence, 4),
        },
        "drift_trend": {
            "profiles_count": len(profiles),
            "average_drift": round(drift_average, 4),
            "max_drift": round(drift_max, 4),
        },
        "action_distribution": action_distribution,
        "loop_health": {
            "acceptance_rate": round(acceptance_rate, 4),
            "regeneration_rate": round(regeneration_rate, 4),
            "observed_vs_synthetic_agreement": round(
                observed_vs_synthetic_agreement, 4
            ),
            "eval_events": len(eval_events),
            "agreement_pairs": len(agreement_scores),
        },
    }


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)


__all__ = ["router"]
