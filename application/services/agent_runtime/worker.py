from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
    NoApprovedActionError,
    PlanOnlyModeError,
    RunBusyError,
    RunNotFoundError,
)


@dataclass(frozen=True)
class AgentWorkerRunResult:
    run_id: str
    status: str
    steps_executed: int
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentRuntimeWorkerService:
    def __init__(self, *, deps: AppDeps, lock_ttl_seconds: int = 30) -> None:
        self._deps = deps
        self._runtime = AgentRuntimeService(
            deps=deps, lock_ttl_seconds=lock_ttl_seconds
        )

    def tick_client(
        self,
        *,
        client_id: str,
        user_id: Optional[str],
        max_runs: int = 10,
        max_steps_per_run: int = 5,
    ) -> Dict[str, Any]:
        max_runs = max(1, min(int(max_runs), 100))
        max_steps_per_run = max(1, min(int(max_steps_per_run), 50))
        runnable = self._deps.agent_runs.list_runnable_agent_runs(
            client_id=client_id,
            limit=max_runs,
        )
        run_results: List[AgentWorkerRunResult] = []

        for run in runnable:
            run_id = str(run.get("id") or "")
            steps = 0
            last_error: Optional[str] = None
            status = str(run.get("status") or "unknown")
            while steps < max_steps_per_run:
                try:
                    result = self._runtime.step_once(run_id=run_id, user_id=user_id)
                    status = str(result.run.get("status") or status)
                    steps += 1
                except NoApprovedActionError:
                    reconciled = self._runtime.reconcile_run_status(run_id=run_id)
                    status = str(reconciled.run.get("status") or status)
                    break
                except (RunBusyError, PlanOnlyModeError):
                    break
                except (RunNotFoundError, AgentRuntimeError) as exc:
                    last_error = str(exc)
                    status = "failed"
                    break
            run_results.append(
                AgentWorkerRunResult(
                    run_id=run_id,
                    status=status,
                    steps_executed=steps,
                    last_error=last_error,
                )
            )

        return {
            "client_id": client_id,
            "runs_considered": len(runnable),
            "runs_processed": len(run_results),
            "steps_executed_total": sum(item.steps_executed for item in run_results),
            "results": [item.to_dict() for item in run_results],
        }


__all__ = ["AgentRuntimeWorkerService", "AgentWorkerRunResult"]
