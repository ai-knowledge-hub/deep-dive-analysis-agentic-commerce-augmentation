from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from application.ports.deps import AppDeps


VALIDATION_UNLOCK_COUNT = 10
VALIDATION_ACCURACY_TARGET = 0.75


@dataclass(frozen=True)
class ValidationSummary:
    total_logged: int
    verified_runs: int
    correct_runs: int
    accuracy: float
    unlock_ready: bool
    progress: float
    accuracy_target: float = VALIDATION_ACCURACY_TARGET

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_logged": self.total_logged,
            "verified_runs": self.verified_runs,
            "correct_runs": self.correct_runs,
            "accuracy": self.accuracy,
            "unlock_ready": self.unlock_ready,
            "progress": self.progress,
            "accuracy_target": self.accuracy_target,
        }


class ExperimentValidationService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def log_validation(
        self,
        *,
        experiment_id: str,
        variant_id: Optional[str],
        client_id: str,
        platform: Optional[str],
        query_text: Optional[str],
        observed_products: Optional[list[str]],
        observed_winner_variant_id: Optional[str],
        observed_position: Optional[int],
        notes: Optional[str],
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")

        if variant_id:
            variant = self._deps.experiments.get_variant(variant_id=variant_id)
            if not variant or variant.get("experiment_id") != experiment_id:
                raise ValueError("variant not found for experiment")

        brand_id = experiment.get("brand_id")
        product_id = experiment.get("product_id")
        is_correct = None
        if observed_winner_variant_id:
            is_correct = bool(variant_id and observed_winner_variant_id == variant_id)

        validation = self._deps.experiment_validations.create_validation(
            experiment_id=experiment_id,
            variant_id=variant_id,
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            platform=platform,
            query_text=query_text,
            observed_products=observed_products,
            observed_winner_variant_id=observed_winner_variant_id,
            observed_position=observed_position,
            notes=notes,
            is_correct=is_correct,
            created_at=created_at,
        )

        if brand_id:
            summary = self._brand_summary(brand_id=brand_id, client_id=client_id)
            self._deps.experiment_calibrations.upsert_calibration(
                brand_id=brand_id,
                client_id=client_id,
                verified_runs=summary.verified_runs,
                accuracy=summary.accuracy,
                metadata={
                    "total_logged": summary.total_logged,
                    "correct_runs": summary.correct_runs,
                },
            )

        return validation

    def experiment_summary(
        self, *, experiment_id: str, client_id: str
    ) -> ValidationSummary:
        total_logged = self._deps.experiment_validations.count_validations(
            experiment_id=experiment_id, client_id=client_id
        )
        summary = self._deps.experiment_validations.accuracy_summary(
            experiment_id=experiment_id, client_id=client_id
        )
        return self._build_summary(total_logged, summary)

    def brand_summary(self, *, brand_id: str, client_id: str) -> ValidationSummary:
        return self._brand_summary(brand_id=brand_id, client_id=client_id)

    def _brand_summary(self, *, brand_id: str, client_id: str) -> ValidationSummary:
        total_logged = self._deps.experiment_validations.count_validations(
            brand_id=brand_id, client_id=client_id
        )
        summary = self._deps.experiment_validations.accuracy_summary(
            brand_id=brand_id, client_id=client_id
        )
        return self._build_summary(total_logged, summary)

    def _build_summary(self, total_logged: int, summary: Dict[str, Any]) -> ValidationSummary:
        verified_runs = int(summary.get("verified_runs") or 0)
        correct_runs = int(summary.get("correct_runs") or 0)
        accuracy = float(summary.get("accuracy") or 0.0)
        unlock_ready = (
            verified_runs >= VALIDATION_UNLOCK_COUNT
            and accuracy >= VALIDATION_ACCURACY_TARGET
        )
        progress = min(verified_runs / VALIDATION_UNLOCK_COUNT, 1.0)
        return ValidationSummary(
            total_logged=total_logged,
            verified_runs=verified_runs,
            correct_runs=correct_runs,
            accuracy=accuracy,
            unlock_ready=unlock_ready,
            progress=progress,
        )


__all__ = [
    "ExperimentValidationService",
    "ValidationSummary",
    "VALIDATION_UNLOCK_COUNT",
    "VALIDATION_ACCURACY_TARGET",
]
