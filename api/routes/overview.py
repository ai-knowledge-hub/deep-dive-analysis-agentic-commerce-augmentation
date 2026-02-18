from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter

from api.utils.tenancy import require_client_id
from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json
from infrastructure.db.search.query_batteries import list_batteries
from application.services.query_battery.service import QueryBatteryService
import infrastructure.db.search.query_batteries as query_batteries_repo
from infrastructure.db.experiment.experiment_validations import accuracy_summary
from infrastructure.db.search.simulation_runs import list_lessons
from infrastructure.db.experiment.experiment_recommendations import list_recommendations

router = APIRouter(prefix="/overview", tags=["overview"])


def _range_clause(
    range_days: int, column: str = "created_at"
) -> Tuple[str, Tuple[Any, ...]]:
    if range_days <= 0:
        return "", tuple()
    return f"AND {column} >= datetime('now', ?)", (f"-{range_days} days",)


def _date_key(value: str | None) -> str:
    if not value:
        return ""
    return value.split(" ")[0]


def _parse_protocol_readiness(result: Dict[str, Any]) -> Optional[int]:
    readiness = result.get("protocol_readiness") or []
    if not isinstance(readiness, list):
        return None
    for preferred in ("ucp", "acp"):
        for entry in readiness:
            if entry.get("protocol") != preferred:
                continue
            issues = entry.get("issues") or []
            for issue in issues:
                if issue.get("field") in {"ucp_readiness_score", "acp_readiness_score"}:
                    message = issue.get("message") or ""
                    if isinstance(message, str):
                        import re

                        match = re.search(r"(\\d{1,3})\\s*/\\s*100", message)
                        if match:
                            try:
                                return int(match.group(1))
                            except ValueError:
                                return None
    return None


def _aggregate_series(items: List[Tuple[str, float]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[float]] = {}
    for date, value in items:
        if not date:
            continue
        buckets.setdefault(date, []).append(value)
    return [
        {"date": key, "value": sum(values) / len(values)}
        for key, values in sorted(buckets.items())
    ]


@router.get("/summary")
def overview_summary(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    scope: str = "client",
    range_days: int = 30,
) -> Dict[str, Any]:
    client_id = require_client_id(client_id, user_id)
    conn = get_connection()
    range_clause, range_params = _range_clause(range_days, "created_at")

    latest_metric = conn.execute(
        """
        SELECT em.metrics_json, em.created_at
        FROM experiment_metrics em
        JOIN experiments e ON e.id = em.experiment_id
        WHERE e.client_id = ?
        ORDER BY em.created_at DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()
    latest_metrics = (
        from_json(latest_metric["metrics_json"], default={}) if latest_metric else {}
    )
    latest_metric_at = latest_metric["created_at"] if latest_metric else None

    validation = accuracy_summary(client_id=client_id)
    required_runs = 10
    unlock_ready = (
        validation.get("verified_runs", 0) >= required_runs
        and validation.get("accuracy", 0) >= 0.75
    )

    simulation_rows = conn.execute(
        f"""
        SELECT result_json
        FROM simulation_runs
        WHERE client_id = ?
        {range_clause}
        ORDER BY created_at DESC
        """,
        (client_id, *range_params),
    ).fetchall()
    lifts: List[float] = []
    protocol_scores: List[int] = []
    for row in simulation_rows:
        result = from_json(row["result_json"], default={})
        lift_summary = result.get("lift_summary") or {}
        delta_points = lift_summary.get("delta_points")
        if isinstance(delta_points, (int, float)):
            lifts.append(delta_points / 100.0)
        readiness = _parse_protocol_readiness(result)
        if isinstance(readiness, int):
            protocol_scores.append(readiness)

    avg_lift = (sum(lifts) / len(lifts)) if lifts else None

    evidence_rows = conn.execute(
        f"""
        SELECT record_json
        FROM replay_records
        WHERE client_id = ? AND run_type = 'evidence.analyze'
        {_range_clause(range_days, "created_at")[0]}
        """,
        (client_id, *_range_clause(range_days, "created_at")[1]),
    ).fetchall()
    evidence_items = 0
    for row in evidence_rows:
        record = from_json(row["record_json"], default={})
        outputs = record.get("outputs") or {}
        count = outputs.get("count")
        if isinstance(count, int):
            evidence_items += count

    battery_service = QueryBatteryService(repo=query_batteries_repo)
    latest_battery = list_batteries(client_id=client_id, limit=1)
    battery_metrics = (
        battery_service.get_metrics(battery_id=latest_battery[0]["id"])
        if latest_battery
        else {}
    )

    protocol_readiness = None
    if latest_metrics.get("avg_protocol_readiness_score") is not None:
        try:
            protocol_readiness = int(latest_metrics.get("avg_protocol_readiness_score"))
        except (TypeError, ValueError):
            protocol_readiness = None
    elif protocol_scores:
        protocol_readiness = int(sum(protocol_scores) / len(protocol_scores))

    return {
        "scope": scope,
        "range_days": range_days,
        "kpis": {
            "experiments": {
                "latest_win_rate": latest_metrics.get("win_rate"),
                "latest_avg_score": latest_metrics.get("avg_score"),
                "last_updated": latest_metric_at,
            },
            "validation": {
                "accuracy": validation.get("accuracy"),
                "verified_runs": validation.get("verified_runs"),
                "required_runs": required_runs,
                "unlock_ready": unlock_ready,
            },
            "simulation": {
                "avg_lift": avg_lift,
                "runs": len(simulation_rows),
                "lessons": len(list_lessons(client_id=client_id, limit=50)),
            },
            "evidence": {
                "avg_lift": None,
                "evidence_items": evidence_items,
            },
            "battery_health": {
                "enabled_queries": battery_metrics.get("enabled_queries"),
                "redundancy_rate": battery_metrics.get("redundancy_rate"),
                "coverage_score": (
                    (battery_metrics.get("quality_score") or 0) / 100
                    if battery_metrics
                    else None
                ),
            },
            "protocol_readiness": {"score": protocol_readiness},
        },
    }


@router.get("/timeseries")
def overview_timeseries(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    scope: str = "client",
    range_days: int = 30,
) -> Dict[str, Any]:
    client_id = require_client_id(client_id, user_id)
    conn = get_connection()
    range_clause, range_params = _range_clause(range_days, "em.created_at")

    experiment_rows = conn.execute(
        f"""
        SELECT em.metrics_json, em.created_at
        FROM experiment_metrics em
        JOIN experiments e ON e.id = em.experiment_id
        WHERE e.client_id = ?
        {range_clause}
        ORDER BY em.created_at ASC
        """,
        (client_id, *range_params),
    ).fetchall()
    win_rate_points: List[Tuple[str, float]] = []
    avg_score_points: List[Tuple[str, float]] = []
    for row in experiment_rows:
        metrics = from_json(row["metrics_json"], default={})
        date = _date_key(row["created_at"])
        win_rate = metrics.get("win_rate")
        avg_score = metrics.get("avg_score")
        if isinstance(win_rate, (int, float)):
            win_rate_points.append((date, float(win_rate)))
        if isinstance(avg_score, (int, float)):
            avg_score_points.append((date, float(avg_score)))

    validation_rows = conn.execute(
        f"""
        SELECT is_correct, created_at
        FROM experiment_validations
        WHERE client_id = ? AND is_correct IS NOT NULL
        {_range_clause(range_days, "created_at")[0]}
        ORDER BY created_at ASC
        """,
        (client_id, *_range_clause(range_days, "created_at")[1]),
    ).fetchall()
    validation_bucket: Dict[str, Dict[str, int]] = {}
    for row in validation_rows:
        date = _date_key(row["created_at"])
        bucket = validation_bucket.setdefault(date, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if row["is_correct"]:
            bucket["correct"] += 1
    validation_accuracy = [
        {
            "date": date,
            "value": (counts["correct"] / counts["total"]) if counts["total"] else 0,
        }
        for date, counts in sorted(validation_bucket.items())
    ]

    simulation_rows = conn.execute(
        f"""
        SELECT result_json, created_at
        FROM simulation_runs
        WHERE client_id = ?
        {_range_clause(range_days, "created_at")[0]}
        ORDER BY created_at ASC
        """,
        (client_id, *_range_clause(range_days, "created_at")[1]),
    ).fetchall()
    simulation_points: List[Tuple[str, float]] = []
    for row in simulation_rows:
        result = from_json(row["result_json"], default={})
        lift_summary = result.get("lift_summary") or {}
        delta_points = lift_summary.get("delta_points")
        if isinstance(delta_points, (int, float)):
            simulation_points.append(
                (_date_key(row["created_at"]), delta_points / 100.0)
            )

    belief_rows = conn.execute(
        f"""
        SELECT created_at
        FROM brand_beliefs
        WHERE client_id = ?
        {_range_clause(range_days, "created_at")[0]}
        """,
        (client_id, *_range_clause(range_days, "created_at")[1]),
    ).fetchall()
    belief_bucket: Dict[str, int] = {}
    for row in belief_rows:
        date = _date_key(row["created_at"])
        belief_bucket[date] = belief_bucket.get(date, 0) + 1
    belief_count = [
        {"date": date, "value": count} for date, count in sorted(belief_bucket.items())
    ]

    return {
        "range_days": range_days,
        "series": {
            "win_rate": _aggregate_series(win_rate_points),
            "avg_score": _aggregate_series(avg_score_points),
            "validation_accuracy": validation_accuracy,
            "simulation_lift": _aggregate_series(simulation_points),
            "evidence_lift": [],
            "belief_count": belief_count,
        },
    }


@router.get("/changes")
def overview_changes(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    scope: str = "client",
    range_days: int = 30,
) -> Dict[str, Any]:
    client_id = require_client_id(client_id, user_id)
    conn = get_connection()
    range_clause, range_params = _range_clause(range_days, "created_at")

    latest_experiment = conn.execute(
        """
        SELECT * FROM experiments
        WHERE client_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()

    latest_metric = None
    if latest_experiment:
        latest_metric = conn.execute(
            """
            SELECT * FROM experiment_metrics
            WHERE experiment_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (latest_experiment["id"],),
        ).fetchone()

    latest_simulation_lessons = list_lessons(client_id=client_id, limit=1)
    latest_lesson = latest_simulation_lessons[0] if latest_simulation_lessons else None

    simulation_rows = conn.execute(
        f"""
        SELECT result_json
        FROM simulation_runs
        WHERE client_id = ?
        {_range_clause(range_days, "created_at")[0]}
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (client_id, *_range_clause(range_days, "created_at")[1]),
    ).fetchall()
    gap_counts: Dict[str, int] = {}
    for row in simulation_rows:
        result = from_json(row["result_json"], default={})
        gap_analysis = result.get("gap_analysis") or []
        if not isinstance(gap_analysis, list):
            continue
        for gap in gap_analysis:
            for signal in gap.get("missing_signals") or []:
                gap_counts[signal] = gap_counts.get(signal, 0) + 1
    top_gap_signals = [
        {"signal": signal, "count": count}
        for signal, count in sorted(
            gap_counts.items(), key=lambda item: item[1], reverse=True
        )[:4]
    ]

    next_test = None
    if latest_experiment:
        recs = list_recommendations(experiment_id=latest_experiment["id"], limit=1)
        if recs:
            next_test = recs[0].get("recommendation")

    return {
        "latest_experiment": {
            "id": latest_experiment["id"] if latest_experiment else None,
            "name": latest_experiment["name"] if latest_experiment else None,
            "winner_label": None,
            "lift": (
                from_json(latest_metric["metrics_json"], default={}).get("win_rate")
                if latest_metric
                else None
            ),
            "created_at": latest_experiment["created_at"]
            if latest_experiment
            else None,
        },
        "latest_simulation_lesson": {
            "summary": latest_lesson.get("lesson") if latest_lesson else None,
            "confidence": None,
            "created_at": latest_lesson.get("created_at") if latest_lesson else None,
        }
        if latest_lesson
        else None,
        "top_gap_signals": top_gap_signals,
        "next_test": next_test,
    }
