from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from application.ports.deps import AppDeps
from application.services.experiment.runner import ExperimentRunner, ExperimentRunResult


def _utc_now() -> datetime:
    return datetime.utcnow()


def _format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _next_run_at(*, base: datetime, interval_minutes: int) -> str:
    return _format_dt(base + timedelta(minutes=interval_minutes))


@dataclass(frozen=True)
class ScheduleUpdateResult:
    experiment_id: str
    schedule_enabled: bool
    schedule_interval_minutes: Optional[int]
    next_run_at: Optional[str]


@dataclass(frozen=True)
class ScheduleRunResult:
    experiment_id: str
    runs: list[ExperimentRunResult]
    last_run_at: str
    next_run_at: Optional[str]


class ExperimentScheduler:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._runner = ExperimentRunner(deps=deps)

    def update_schedule(
        self,
        *,
        experiment_id: str,
        client_id: str,
        enabled: bool,
        interval_minutes: Optional[int],
    ) -> ScheduleUpdateResult:
        if enabled and not interval_minutes:
            raise ValueError("interval_minutes is required when schedule is enabled")

        next_run = (
            _next_run_at(base=_utc_now(), interval_minutes=interval_minutes)
            if enabled and interval_minutes
            else None
        )

        experiment = self._deps.experiments.update_experiment(
            experiment_id=experiment_id,
            client_id=client_id,
            schedule_enabled=enabled,
            schedule_interval_minutes=interval_minutes,
            next_run_at=next_run,
        )
        if not experiment:
            raise ValueError("experiment not found")

        return ScheduleUpdateResult(
            experiment_id=experiment["id"],
            schedule_enabled=bool(experiment.get("schedule_enabled")),
            schedule_interval_minutes=experiment.get("schedule_interval_minutes"),
            next_run_at=experiment.get("next_run_at"),
        )

    def run_backfill(
        self,
        *,
        experiment_id: str,
        client_id: str,
        user_id: Optional[str] = None,
    ) -> ScheduleRunResult:
        results = self._runner.run_experiment_for_all_variants(
            experiment_id=experiment_id,
            client_id=client_id,
            user_id=user_id,
        )
        now = _utc_now()

        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")

        next_run = None
        interval = experiment.get("schedule_interval_minutes")
        if experiment.get("schedule_enabled") and interval:
            next_run = _next_run_at(base=now, interval_minutes=int(interval))

        self._deps.experiments.update_experiment(
            experiment_id=experiment_id,
            client_id=client_id,
            last_run_at=_format_dt(now),
            next_run_at=next_run,
        )

        return ScheduleRunResult(
            experiment_id=experiment_id,
            runs=results,
            last_run_at=_format_dt(now),
            next_run_at=next_run,
        )

    def run_due(
        self, *, limit: int = 20, client_id: Optional[str] = None
    ) -> list[ScheduleRunResult]:
        due = self._deps.experiments.list_due_experiments(
            client_id=client_id, limit=limit
        )
        results: list[ScheduleRunResult] = []
        for experiment in due:
            results.append(
                self.run_backfill(
                    experiment_id=experiment["id"],
                    client_id=experiment["client_id"],
                )
            )
        return results


__all__ = ["ExperimentScheduler", "ScheduleUpdateResult", "ScheduleRunResult"]
