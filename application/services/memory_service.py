from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps

MIN_QUALITY_THRESHOLD = 0.65
MIN_SUPPORT_THRESHOLD = 2
logger = logging.getLogger(__name__)


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


class MemoryService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def distill(
        self,
        *,
        client_id: str,
        artifact_type: str,
        payload: Dict[str, Any],
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        vertical: Optional[str] = None,
        quality_score: Optional[float] = None,
        support_count: Optional[int] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_quality = _clamp(
            float(quality_score)
            if quality_score is not None
            else self._score_payload(payload)
        )
        resolved_support = max(
            0,
            int(
                support_count
                if support_count is not None
                else payload.get("support_count", 1)
            ),
        )
        contradiction_penalty = self._contradiction_penalty(
            client_id=client_id, brand_id=brand_id
        )
        adjusted_quality = _clamp(resolved_quality - contradiction_penalty)
        artifact = self._deps.memory_artifacts.create_memory_artifact(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            vertical=vertical,
            artifact_type=artifact_type,
            payload=payload,
            quality_score=adjusted_quality,
            support_count=resolved_support,
            source=source,
        )
        artifact["is_promoted"] = bool(
            adjusted_quality >= MIN_QUALITY_THRESHOLD
            and resolved_support >= MIN_SUPPORT_THRESHOLD
        )
        artifact["quality_penalty"] = contradiction_penalty
        logger.info(
            "memory_distill client_id=%s brand_id=%s product_id=%s artifact_type=%s quality=%.4f support=%d promoted=%s source=%s",
            client_id,
            brand_id,
            product_id,
            artifact_type,
            adjusted_quality,
            resolved_support,
            artifact["is_promoted"],
            source,
        )
        return artifact

    def retrieve(
        self,
        *,
        client_id: str,
        artifact_type: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        vertical: Optional[str] = None,
        min_quality: float = MIN_QUALITY_THRESHOLD,
        freshness_days: int = 180,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        base = self._deps.memory_artifacts.list_memory_artifacts(
            client_id=client_id,
            artifact_type=artifact_type,
            min_quality=min_quality,
            limit=max(limit * 5, 100),
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, freshness_days))
        product_bucket: List[Dict[str, Any]] = []
        brand_vertical_bucket: List[Dict[str, Any]] = []
        vertical_bucket: List[Dict[str, Any]] = []
        fallback_bucket: List[Dict[str, Any]] = []
        for artifact in base:
            created_at = artifact.get("created_at")
            if isinstance(created_at, str) and created_at:
                parsed = _parse_timestamp(created_at)
                if parsed and parsed < cutoff:
                    continue
            if product_id and artifact.get("product_id") == product_id:
                product_bucket.append(artifact)
            elif (
                brand_id
                and vertical
                and artifact.get("brand_id") == brand_id
                and artifact.get("vertical") == vertical
            ):
                brand_vertical_bucket.append(artifact)
            elif vertical and artifact.get("vertical") == vertical:
                vertical_bucket.append(artifact)
            else:
                fallback_bucket.append(artifact)
        ordered = (
            product_bucket + brand_vertical_bucket + vertical_bucket + fallback_bucket
        )
        selected = ordered[:limit]
        logger.info(
            "memory_retrieve client_id=%s brand_id=%s product_id=%s artifact_type=%s vertical=%s selected=%d min_quality=%.2f freshness_days=%d",
            client_id,
            brand_id,
            product_id,
            artifact_type,
            vertical,
            len(selected),
            min_quality,
            freshness_days,
        )
        return selected

    def _score_payload(self, payload: Dict[str, Any]) -> float:
        confidence = payload.get("confidence")
        support_size = payload.get("support_size", payload.get("support_count", 1))
        confidence_score = (
            _clamp(float(confidence)) if isinstance(confidence, (int, float)) else 0.6
        )
        support_score = _clamp(min(1.0, float(support_size) / 10.0))
        text_fields = [
            _as_text(payload.get("pattern")),
            _as_text(payload.get("summary")),
            _as_text(payload.get("query_template")),
            _as_text(payload.get("copy_template")),
        ]
        text_present = any(text_fields)
        structure_score = 0.8 if text_present else 0.5
        return _clamp(
            (confidence_score * 0.45) + (support_score * 0.3) + (structure_score * 0.25)
        )

    def _contradiction_penalty(
        self, *, client_id: str, brand_id: Optional[str]
    ) -> float:
        if not brand_id:
            return 0.0
        summary = self._deps.experiment_validations.accuracy_summary(
            client_id=client_id,
            brand_id=brand_id,
        )
        verified = int(summary.get("verified_runs") or 0)
        accuracy = float(summary.get("accuracy") or 0.0)
        if verified >= 10 and accuracy < 0.4:
            return 0.2
        if verified >= 5 and accuracy < 0.5:
            return 0.1
        return 0.0


def _parse_timestamp(value: str) -> datetime | None:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None


__all__ = ["MemoryService", "MIN_QUALITY_THRESHOLD", "MIN_SUPPORT_THRESHOLD"]
