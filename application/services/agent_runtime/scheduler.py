from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.worker import AgentRuntimeWorkerService


@dataclass(frozen=True)
class AgentSchedulerCycleResult:
    cycle: int
    clients_processed: int
    runs_processed_total: int
    steps_executed_total: int
    summaries: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentRuntimeSchedulerService:
    def __init__(self, *, deps: AppDeps, lock_ttl_seconds: int = 30) -> None:
        self._deps = deps
        self._worker = AgentRuntimeWorkerService(
            deps=deps, lock_ttl_seconds=lock_ttl_seconds
        )

    def run_once(
        self,
        *,
        client_id: Optional[str] = None,
        user_id: Optional[str] = "agent-runtime-scheduler",
        max_clients: int = 100,
        max_runs_per_client: int = 10,
        max_steps_per_run: int = 5,
    ) -> Dict[str, Any]:
        client_ids = self._resolve_client_ids(
            client_id=client_id, max_clients=max_clients
        )
        summaries: List[Dict[str, Any]] = []
        for current_client_id in client_ids:
            summary = self._worker.tick_client(
                client_id=current_client_id,
                user_id=user_id,
                max_runs=max_runs_per_client,
                max_steps_per_run=max_steps_per_run,
            )
            summaries.append(summary)

        return {
            "clients_considered": len(client_ids),
            "clients_processed": len(summaries),
            "runs_processed_total": sum(
                int(item.get("runs_processed") or 0) for item in summaries
            ),
            "steps_executed_total": sum(
                int(item.get("steps_executed_total") or 0) for item in summaries
            ),
            "summaries": summaries,
        }

    def run_forever(
        self,
        *,
        interval_seconds: int = 30,
        client_id: Optional[str] = None,
        user_id: Optional[str] = "agent-runtime-scheduler",
        max_clients: int = 100,
        max_runs_per_client: int = 10,
        max_steps_per_run: int = 5,
        max_cycles: Optional[int] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> Dict[str, Any]:
        interval = max(1, int(interval_seconds))
        cycle = 0
        cycle_results: List[Dict[str, Any]] = []
        while True:
            cycle += 1
            started = time.monotonic()
            summary = self.run_once(
                client_id=client_id,
                user_id=user_id,
                max_clients=max_clients,
                max_runs_per_client=max_runs_per_client,
                max_steps_per_run=max_steps_per_run,
            )
            cycle_result = AgentSchedulerCycleResult(
                cycle=cycle,
                clients_processed=int(summary.get("clients_processed") or 0),
                runs_processed_total=int(summary.get("runs_processed_total") or 0),
                steps_executed_total=int(summary.get("steps_executed_total") or 0),
                summaries=list(summary.get("summaries") or []),
            ).to_dict()
            cycle_results.append(cycle_result)
            if max_cycles is not None and cycle >= max(1, int(max_cycles)):
                break
            elapsed = time.monotonic() - started
            remaining = max(0.0, float(interval) - elapsed)
            sleep_fn(remaining)

        return {
            "cycles_completed": cycle,
            "interval_seconds": interval,
            "client_scope": client_id,
            "cycle_results": cycle_results,
        }

    def _resolve_client_ids(
        self, *, client_id: Optional[str], max_clients: int
    ) -> List[str]:
        if client_id:
            return [str(client_id)]
        limit = max(1, min(int(max_clients), 1000))
        try:
            clients = self._deps.clients.list_clients(limit=limit)
        except TypeError:
            clients = self._deps.clients.list_clients()
        values: List[str] = []
        for item in list(clients)[:limit]:
            current = str(item.get("id") or "").strip()
            if current:
                values.append(current)
        return values


__all__ = ["AgentRuntimeSchedulerService", "AgentSchedulerCycleResult"]
