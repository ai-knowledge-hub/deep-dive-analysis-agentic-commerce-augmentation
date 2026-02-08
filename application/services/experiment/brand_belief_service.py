from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import BrandBeliefsStore


class BrandBeliefService:
    def __init__(self, *, repo: BrandBeliefsStore) -> None:
        self._repo = repo

    def create_belief(
        self,
        *,
        client_id: str,
        brand_id: str,
        product_id: Optional[str] = None,
        hypothesis: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
        recommendation: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._repo.create_belief(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            hypothesis=hypothesis,
            evidence=evidence,
            recommendation=recommendation,
            confidence=confidence,
            metadata=metadata,
        )

    def list_beliefs(
        self,
        *,
        client_id: str,
        brand_id: str,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        return self._repo.list_beliefs(
            client_id=client_id, brand_id=brand_id, limit=limit
        )

    def latest_belief(
        self,
        *,
        client_id: str,
        brand_id: str,
    ) -> Dict[str, Any] | None:
        return self._repo.latest_belief(client_id=client_id, brand_id=brand_id)


__all__ = ["BrandBeliefService"]
