"""Run lifecycle controls kept separate from the execution loop."""

from __future__ import annotations

from typing import Any

from application.services.agent_runtime.runtime.audit import record_run_event
from application.services.agent_runtime.runtime.errors import AgentRuntimeError
from application.services.agent_runtime.runtime.status import (
    record_operator_pause_condition,
)
from application.services.agent_runtime.registry import run_mode_supported


def start_run_control(service: Any, run_id: str) -> tuple[dict[str, Any], str | None]:
    run = service._require_run(run_id)
    service._assert_not_terminal(run, action="started")
    run_mode = str(run.get("run_mode") or "plan_only").strip().lower()
    if not run_mode_supported(run_mode):
        raise AgentRuntimeError(f"Unsupported run_mode: {run_mode}")
    if run_mode == "plan_only":
        updated = service._transition_run(run, status="planned", action="started")
        return updated or run, (
            "Run is in plan-only mode. Actions can be approved/rejected but not "
            "executed."
        )
    updated = service._transition_run(run, status="running", action="started")
    record_run_event(
        deps=service._deps,
        run_id=run_id,
        sequence=0,
        event_type="run_started",
        status="running",
        note="Run started",
    )
    return updated or run, None


def pause_run_control(service: Any, run_id: str) -> dict[str, Any]:
    run = service._require_run(run_id)
    service._assert_not_terminal(run, action="paused")
    updated = service._transition_run(
        run, status="paused", action="paused", error=run.get("error")
    )
    record_run_event(
        deps=service._deps,
        run_id=run_id,
        sequence=0,
        event_type="run_paused",
        status="paused",
        note="Run paused",
    )
    record_operator_pause_condition(deps=service._deps, run=updated or run)
    return updated or run


def cancel_run_control(service: Any, run_id: str) -> dict[str, Any]:
    run = service._require_run(run_id)
    if service._normalized_status(run) in {"canceled", "completed", "failed"}:
        raise AgentRuntimeError("Run is already terminal")
    updated = service._transition_run(run, status="canceled", action="canceled")
    record_run_event(
        deps=service._deps,
        run_id=run_id,
        sequence=0,
        event_type="run_canceled",
        status="canceled",
        note="Run canceled",
    )
    return updated or run


__all__ = ["cancel_run_control", "pause_run_control", "start_run_control"]
