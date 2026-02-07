from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.memory_service import MemoryService
from infrastructure.db.connection import get_connection


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


class LoopMaintenanceService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps
        self._memory = MemoryService(deps=deps)

    def refresh_calibration_profiles(
        self,
        *,
        client_id: str,
        brand_id: Optional[str] = None,
        lookback_days: int = 30,
    ) -> List[Dict[str, Any]]:
        conn = get_connection()
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))
        ).strftime("%Y-%m-%d %H:%M:%S")
        filters = ["vj.client_id = ?", "vr.created_at >= ?"]
        params: list[Any] = [client_id, cutoff]
        if brand_id:
            filters.append("vj.brand_id = ?")
            params.append(brand_id)
        where_clause = " AND ".join(filters)
        rows = conn.execute(
            f"""
            SELECT
                lower(vr.provider) AS provider,
                vj.brand_id AS brand_id,
                vj.mode AS mode,
                AVG(COALESCE(vr.score, 0.0)) AS avg_score,
                COUNT(1) AS count_rows
            FROM validation_results vr
            JOIN validation_jobs vj ON vj.id = vr.job_id
            WHERE {where_clause}
            GROUP BY lower(vr.provider), vj.brand_id, vj.mode
            """,
            params,
        ).fetchall()
        grouped: dict[tuple[str, Optional[str]], Dict[str, Any]] = defaultdict(
            lambda: {
                "synthetic_avg": 0.0,
                "synthetic_count": 0,
                "observed_avg": 0.0,
                "observed_count": 0,
            }
        )
        for row in rows:
            provider = str(row["provider"] or "").strip().lower()
            if not provider:
                continue
            key = (provider, row["brand_id"])
            mode = str(row["mode"] or "").strip().lower()
            avg_score = float(row["avg_score"] or 0.0)
            count_rows = int(row["count_rows"] or 0)
            if mode == "external":
                grouped[key]["observed_avg"] = avg_score
                grouped[key]["observed_count"] = count_rows
            else:
                grouped[key]["synthetic_avg"] = avg_score
                grouped[key]["synthetic_count"] = count_rows

        updated: list[Dict[str, Any]] = []
        for (provider, row_brand_id), values in grouped.items():
            synthetic_avg = float(values["synthetic_avg"])
            observed_avg = float(values["observed_avg"])
            synthetic_count = int(values["synthetic_count"])
            observed_count = int(values["observed_count"])
            if synthetic_count == 0 and observed_count == 0:
                continue
            agreement = 1.0 - abs(observed_avg - synthetic_avg)
            drift_score = 1.0 - _clamp(agreement)
            score_weight = _clamp(
                1.0 + ((observed_avg - synthetic_avg) * 0.4), 0.6, 1.4
            )
            confidence_weight = _clamp(
                1.0
                + (
                    (observed_count - synthetic_count)
                    / max(1.0, synthetic_count + observed_count)
                ),
                0.7,
                1.4,
            )
            metric_weights = {
                "score_weight": round(score_weight, 4),
                "confidence_weight": round(confidence_weight, 4),
                "uncertainty_weight": round(
                    _clamp(1.0 + drift_score * 0.5, 0.8, 1.5), 4
                ),
                "gain_weight": round(_clamp(1.1 - drift_score * 0.4, 0.6, 1.3), 4),
            }
            profile = self._deps.calibration_profiles.upsert_calibration_profile(
                client_id=client_id,
                brand_id=row_brand_id,
                provider=provider,
                metric_weights=metric_weights,
                drift_score=round(drift_score, 4),
            )
            updated.append(profile)
        return updated

    def distill_recent_beliefs(
        self,
        *,
        client_id: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        min_confidence: float = 0.7,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        revisions = self._deps.belief_revisions.list_belief_revisions(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            limit=max(1, int(limit)),
        )
        dedup: dict[tuple[str, Optional[str], Optional[str]], Dict[str, Any]] = {}
        for revision in revisions:
            confidence = float(revision.get("confidence") or 0.0)
            if confidence < min_confidence:
                continue
            key = (
                str(revision.get("hypothesis_key") or ""),
                revision.get("brand_id"),
                revision.get("product_id"),
            )
            if key not in dedup:
                dedup[key] = revision

        artifacts: list[Dict[str, Any]] = []
        for revision in dedup.values():
            evidence_ref = revision.get("evidence_ref") or {}
            provider = str(evidence_ref.get("provider") or "").strip().lower()
            vertical = str(evidence_ref.get("vertical") or "").strip() or None
            payload = {
                "hypothesis_key": revision.get("hypothesis_key"),
                "posterior": revision.get("posterior"),
                "confidence": revision.get("confidence"),
                "support_count": max(1, int(evidence_ref.get("support_size", 1))),
                "summary": f"Belief trend for {revision.get('hypothesis_key')}",
                "source_revision_id": revision.get("id"),
                "provider": provider or None,
            }
            artifact = self._memory.distill(
                client_id=client_id,
                brand_id=revision.get("brand_id"),
                product_id=revision.get("product_id"),
                vertical=vertical,
                artifact_type="audience_pattern",
                payload=payload,
                quality_score=float(revision.get("confidence") or 0.0),
                support_count=max(1, int(evidence_ref.get("support_size", 1))),
                source="belief_revision",
            )
            artifacts.append(artifact)
        return artifacts


__all__ = ["LoopMaintenanceService"]
