"""Run learning-loop maintenance jobs.

Usage:
  DATABASE_PATH=./tmp/local.db uv run scripts/run_learning_loop_maintenance.py --lookback-days 30
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List

from api.composition import default_deps
from application.services.loop_maintenance_service import LoopMaintenanceService
from shared.db.connection import DEFAULT_DB_PATH


def _run_for_client(
    service: LoopMaintenanceService,
    *,
    client_id: str,
    lookback_days: int,
    min_confidence: float,
) -> Dict[str, Any]:
    calibration = service.refresh_calibration_profiles(
        client_id=client_id,
        lookback_days=lookback_days,
    )
    artifacts = service.distill_recent_beliefs(
        client_id=client_id,
        min_confidence=min_confidence,
    )
    return {
        "client_id": client_id,
        "calibration_profiles_updated": len(calibration),
        "memory_artifacts_distilled": len(artifacts),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", type=str, default=None)
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--min-confidence", type=float, default=0.7)
    args = parser.parse_args()

    deps = default_deps()
    deps.init_db()
    service = LoopMaintenanceService(deps=deps)

    results: List[Dict[str, Any]] = []
    if args.client_id:
        results.append(
            _run_for_client(
                service,
                client_id=args.client_id,
                lookback_days=args.lookback_days,
                min_confidence=args.min_confidence,
            )
        )
    else:
        for client in deps.clients.list_clients():
            results.append(
                _run_for_client(
                    service,
                    client_id=str(client.get("id")),
                    lookback_days=args.lookback_days,
                    min_confidence=args.min_confidence,
                )
            )

    print(f"Maintenance processed {len(results)} client(s).")
    for row in results:
        print(
            f"- {row['client_id']}: calibration={row['calibration_profiles_updated']} "
            f"distilled={row['memory_artifacts_distilled']}"
        )

    db_path = os.getenv("DATABASE_PATH") or str(DEFAULT_DB_PATH)
    print(f"Database: {db_path}")


if __name__ == "__main__":
    os.environ.setdefault(
        "DATABASE_PATH", os.getenv("DATABASE_PATH", "./db/discovery.db")
    )
    main()
