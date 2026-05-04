"""Run due experiment schedules.

Usage:
  DATABASE_PATH=./tmp/local.db uv run python -m scripts.ops.run_experiment_schedules --limit 10
"""

from __future__ import annotations

import argparse
import os

from api.composition import default_deps
from application.services.experiment.scheduler import ExperimentScheduler
from shared.db.connection import DEFAULT_DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--client-id", type=str, default=None)
    args = parser.parse_args()

    deps = default_deps()
    deps.init_db()

    scheduler = ExperimentScheduler(deps=deps)
    results = scheduler.run_due(limit=args.limit, client_id=args.client_id)

    print(f"Ran {len(results)} scheduled experiments.")
    for result in results:
        print(
            f"- {result.experiment_id} last_run_at={result.last_run_at} next_run_at={result.next_run_at}"
        )

    db_path = os.getenv("DATABASE_PATH") or str(DEFAULT_DB_PATH)
    print(f"Database: {db_path}")


if __name__ == "__main__":
    os.environ.setdefault("DATABASE_PATH", os.getenv("DATABASE_PATH", "./tmp/local.db"))
    main()
