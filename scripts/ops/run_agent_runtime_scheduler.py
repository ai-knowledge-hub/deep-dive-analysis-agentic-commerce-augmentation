"""Run agent runtime scheduler loop.

Usage:
  DATABASE_PATH=./tmp/local.db uv run python -m scripts.ops.run_agent_runtime_scheduler --once
  DATABASE_PATH=./tmp/local.db uv run python -m scripts.ops.run_agent_runtime_scheduler --interval-seconds 30
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict

from api.composition import default_deps
from application.services.agent_runtime.scheduler import AgentRuntimeSchedulerService
from shared.db.connection import DEFAULT_DB_PATH


def _print_once_summary(summary: Dict[str, Any]) -> None:
    print(
        "Agent runtime scheduler tick: "
        f"clients={summary['clients_processed']}/{summary['clients_considered']} "
        f"runs={summary['runs_processed_total']} "
        f"steps={summary['steps_executed_total']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", type=str, default=None)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("--max-clients", type=int, default=100)
    parser.add_argument("--max-runs-per-client", type=int, default=10)
    parser.add_argument("--max-steps-per-run", type=int, default=5)
    args = parser.parse_args()

    deps = default_deps()
    deps.init_db()
    service = AgentRuntimeSchedulerService(deps=deps)

    if args.once:
        summary = service.run_once(
            client_id=args.client_id,
            user_id="agent-runtime-scheduler",
            max_clients=args.max_clients,
            max_runs_per_client=args.max_runs_per_client,
            max_steps_per_run=args.max_steps_per_run,
        )
        _print_once_summary(summary)
    else:
        print(
            "Starting agent runtime scheduler loop "
            f"(interval={max(1, int(args.interval_seconds))}s, max_cycles={args.max_cycles})"
        )
        result = service.run_forever(
            interval_seconds=args.interval_seconds,
            client_id=args.client_id,
            user_id="agent-runtime-scheduler",
            max_clients=args.max_clients,
            max_runs_per_client=args.max_runs_per_client,
            max_steps_per_run=args.max_steps_per_run,
            max_cycles=args.max_cycles,
        )
        last_cycle = (result.get("cycle_results") or [{}])[-1]
        print(
            "Agent runtime scheduler loop finished: "
            f"cycles={result.get('cycles_completed', 0)} "
            f"runs={last_cycle.get('runs_processed_total', 0)} "
            f"steps={last_cycle.get('steps_executed_total', 0)}"
        )

    db_path = os.getenv("DATABASE_PATH") or str(DEFAULT_DB_PATH)
    print(f"Database: {db_path}")


if __name__ == "__main__":
    os.environ.setdefault("DATABASE_PATH", os.getenv("DATABASE_PATH", "./tmp/local.db"))
    main()
