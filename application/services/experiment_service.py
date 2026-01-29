from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import ExperimentsStore


class ExperimentService:
    def __init__(self, *, repo: ExperimentsStore) -> None:
        self._repo = repo

    def create_experiment(
        self,
        *,
        client_id: str,
        product_id: str,
        name: str,
        battery_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        hypothesis: Optional[Dict[str, Any]] = None,
        competitor_policy: Optional[Dict[str, Any]] = None,
        status: str = "draft",
    ) -> Dict[str, Any]:
        return self._repo.create_experiment(
            client_id=client_id,
            product_id=product_id,
            name=name,
            battery_id=battery_id,
            brand_id=brand_id,
            hypothesis=hypothesis,
            competitor_policy=competitor_policy,
            status=status,
        )

    def list_experiments(
        self,
        *,
        client_id: str,
        product_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        battery_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        return self._repo.list_experiments(
            client_id=client_id,
            product_id=product_id,
            brand_id=brand_id,
            battery_id=battery_id,
            status=status,
            limit=limit,
        )

    def get_experiment(
        self, *, experiment_id: str, client_id: Optional[str] = None
    ) -> Dict[str, Any] | None:
        return self._repo.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )

    def update_experiment(
        self,
        *,
        experiment_id: str,
        client_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        hypothesis: Optional[Dict[str, Any]] = None,
        competitor_policy: Optional[Dict[str, Any]] = None,
        schedule_enabled: Optional[bool] = None,
        schedule_interval_minutes: Optional[int] = None,
        last_run_at: Optional[str] = None,
        next_run_at: Optional[str] = None,
    ) -> Dict[str, Any] | None:
        return self._repo.update_experiment(
            experiment_id=experiment_id,
            client_id=client_id,
            name=name,
            status=status,
            hypothesis=hypothesis,
            competitor_policy=competitor_policy,
            schedule_enabled=schedule_enabled,
            schedule_interval_minutes=schedule_interval_minutes,
            last_run_at=last_run_at,
            next_run_at=next_run_at,
        )

    def add_variant(
        self,
        *,
        experiment_id: str,
        label: str,
        variant_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._repo.add_variant(
            experiment_id=experiment_id,
            label=label,
            variant_type=variant_type,
            payload=payload,
        )

    def list_variants(self, *, experiment_id: str) -> list[Dict[str, Any]]:
        return self._repo.list_variants(experiment_id=experiment_id)


__all__ = ["ExperimentService"]
