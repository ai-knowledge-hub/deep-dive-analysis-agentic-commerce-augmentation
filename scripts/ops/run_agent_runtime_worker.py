"""Run one autonomous tick for agent runtime runs.

Usage:
  DATABASE_PATH=./tmp/local.db uv run python -m scripts.ops.run_agent_runtime_worker --client-id <client>
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List

from api.composition import default_deps
from application.services.agent_runtime.worker import AgentRuntimeWorkerService
from shared.db.connection import DEFAULT_DB_PATH


def _tick_for_client(
    service: AgentRuntimeWorkerService,
    *,
    client_id: str,
    max_runs: int,
    max_steps_per_run: int,
) -> Dict[str, Any]:
    return service.tick_client(
        client_id=client_id,
        user_id="agent-runtime-worker",
        max_runs=max_runs,
        max_steps_per_run=max_steps_per_run,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", type=str, default=None)
    parser.add_argument("--max-runs", type=int, default=10)
    parser.add_argument("--max-steps-per-run", type=int, default=5)
    args = parser.parse_args()

    deps = default_deps()
    deps.init_db()
    service = AgentRuntimeWorkerService(deps=deps)

    results: List[Dict[str, Any]] = []
    if args.client_id:
        results.append(
            _tick_for_client(
                service,
                client_id=args.client_id,
                max_runs=args.max_runs,
                max_steps_per_run=args.max_steps_per_run,
            )
        )
    else:
        for client in deps.clients.list_clients():
            client_id = str(client.get("id") or "")
            if not client_id:
                continue
            results.append(
                _tick_for_client(
                    service,
                    client_id=client_id,
                    max_runs=args.max_runs,
                    max_steps_per_run=args.max_steps_per_run,
                )
            )

    print(f"Agent runtime tick processed {len(results)} client(s).")
    for row in results:
        print(
            f"- {row['client_id']}: runs={row['runs_processed']}/{row['runs_considered']} "
            f"steps={row['steps_executed_total']}"
        )

    db_path = os.getenv("DATABASE_PATH") or str(DEFAULT_DB_PATH)
    print(f"Database: {db_path}")


if __name__ == "__main__":
    os.environ.setdefault("DATABASE_PATH", os.getenv("DATABASE_PATH", "./tmp/local.db"))
    main()
