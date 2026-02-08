from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from application.ports.deps import AppDeps


logger = logging.getLogger(__name__)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def bayesian_posterior(prior: float, likelihood: float) -> float:
    prior = clamp(prior)
    likelihood = clamp(likelihood)
    denominator = (prior * likelihood) + ((1.0 - prior) * (1.0 - likelihood))
    if denominator <= 0:
        return prior
    return clamp((prior * likelihood) / denominator)


class BeliefUpdateService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def update(
        self,
        *,
        client_id: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        hypothesis_key: str,
        evidence: Dict[str, Any],
        prior: Optional[float] = None,
        likelihood: Optional[float] = None,
    ) -> Dict[str, Any]:
        previous = self._deps.belief_revisions.get_latest_belief_revision(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            hypothesis_key=hypothesis_key,
        )
        resolved_prior = (
            clamp(float(prior))
            if prior is not None
            else clamp(float((previous or {}).get("posterior", 0.5)))
        )
        evidence_likelihood = (
            clamp(float(likelihood))
            if likelihood is not None
            else self._weighted_likelihood(
                evidence=evidence, client_id=client_id, brand_id=brand_id
            )
        )
        posterior = bayesian_posterior(resolved_prior, evidence_likelihood)
        confidence = self._confidence_score(
            evidence=evidence,
            likelihood=evidence_likelihood,
            client_id=client_id,
            brand_id=brand_id,
        )
        revision = self._deps.belief_revisions.create_belief_revision(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            hypothesis_key=hypothesis_key,
            prior=resolved_prior,
            likelihood=evidence_likelihood,
            posterior=posterior,
            confidence=confidence,
            evidence_ref=evidence,
        )
        logger.info(
            "belief_update client_id=%s brand_id=%s product_id=%s hypothesis_key=%s prior=%.4f likelihood=%.4f posterior=%.4f confidence=%.4f source=%s provider=%s",
            client_id,
            brand_id,
            product_id,
            hypothesis_key,
            resolved_prior,
            evidence_likelihood,
            posterior,
            confidence,
            str(evidence.get("source") or ""),
            str(evidence.get("provider") or ""),
        )
        return revision

    def _weighted_likelihood(
        self,
        *,
        evidence: Dict[str, Any],
        client_id: str,
        brand_id: Optional[str],
    ) -> float:
        source = str(evidence.get("source") or "synthetic").lower()
        provider = str(evidence.get("provider") or "").lower()
        score = clamp(float(evidence.get("score", 0.5)))
        model_confidence = clamp(float(evidence.get("confidence", 0.5)))
        if source in {"observed", "external"}:
            source_weight = 0.75
        elif source in {"synthetic", "in_app"}:
            source_weight = 0.45
        else:
            source_weight = 0.55
        profile = self._load_calibration(
            client_id=client_id, brand_id=brand_id, provider=provider
        )
        weights = (profile or {}).get("metric_weights") or {}
        score_weight = float(weights.get("score_weight", 1.0))
        confidence_weight = float(weights.get("confidence_weight", 1.0))
        weighted = (
            (score * 0.65 * score_weight)
            + (model_confidence * 0.35 * confidence_weight * source_weight)
            + (score * (1 - source_weight))
        )
        drift_score = float((profile or {}).get("drift_score", 0.0))
        drift_penalty = max(0.0, min(0.25, drift_score * 0.25))
        return clamp(weighted - drift_penalty)

    def _confidence_score(
        self,
        *,
        evidence: Dict[str, Any],
        likelihood: float,
        client_id: str,
        brand_id: Optional[str],
    ) -> float:
        source = str(evidence.get("source") or "synthetic").lower()
        provider = str(evidence.get("provider") or "").lower()
        support_size = max(1, int(evidence.get("support_size", 1)))
        support_factor = clamp(min(1.0, support_size / 10.0))
        source_factor = 0.85 if source in {"observed", "external"} else 0.55
        confidence = clamp(
            (likelihood * 0.5) + (support_factor * 0.25) + (source_factor * 0.25)
        )
        profile = self._load_calibration(
            client_id=client_id, brand_id=brand_id, provider=provider
        )
        drift_score = float((profile or {}).get("drift_score", 0.0))
        return clamp(confidence - max(0.0, min(0.2, drift_score * 0.2)))

    def _load_calibration(
        self,
        *,
        client_id: str,
        brand_id: Optional[str],
        provider: str,
    ) -> Dict[str, Any] | None:
        if not provider:
            return None
        scoped = self._deps.calibration_profiles.get_calibration_profile(
            client_id=client_id,
            brand_id=brand_id,
            provider=provider,
        )
        if scoped:
            return scoped
        return self._deps.calibration_profiles.get_calibration_profile(
            client_id=client_id,
            brand_id=None,
            provider=provider,
        )


__all__ = ["BeliefUpdateService", "bayesian_posterior", "clamp"]
