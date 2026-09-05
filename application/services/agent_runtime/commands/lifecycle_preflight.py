from __future__ import annotations


def command_lifecycle_blockers(
    *, command_type: str, run_status: str, run_mode: str
) -> list[str]:
    blockers: list[str] = []
    terminal = run_status in {"canceled", "cancelled", "completed"}
    if command_type == "step":
        if run_mode == "plan_only":
            blockers.append("Run is plan-only. Switch mode before executing steps.")
        if terminal:
            blockers.append("Run is not executable in its current status.")
    if command_type == "start" and terminal:
        blockers.append("Canceled or completed runs cannot be started.")
    if command_type == "cancel" and terminal:
        blockers.append("Run is already terminal.")
    if command_type in {"change_plan", "retry"} and terminal:
        blockers.append(
            "Terminal runs cannot accept recovery actions; create a new run to continue."
        )
    return blockers


__all__ = ["command_lifecycle_blockers"]
