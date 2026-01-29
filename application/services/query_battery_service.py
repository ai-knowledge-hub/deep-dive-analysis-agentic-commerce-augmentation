from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import QueryBatteriesStore


class QueryBatteryService:
    def __init__(self, *, repo: QueryBatteriesStore) -> None:
        self._repo = repo

    def create_battery(
        self,
        *,
        client_id: str,
        product_id: str,
        name: str,
        purpose: Optional[str] = None,
        generation_mode: Optional[str] = None,
        status: str = "draft",
        brand_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._repo.create_battery(
            client_id=client_id,
            product_id=product_id,
            name=name,
            purpose=purpose,
            generation_mode=generation_mode,
            status=status,
            brand_id=brand_id,
        )

    def list_batteries(
        self,
        *,
        client_id: str,
        product_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        return self._repo.list_batteries(
            client_id=client_id,
            product_id=product_id,
            brand_id=brand_id,
            status=status,
            limit=limit,
        )

    def get_battery(
        self, *, battery_id: str, client_id: Optional[str] = None
    ) -> Dict[str, Any] | None:
        return self._repo.get_battery(battery_id=battery_id, client_id=client_id)

    def update_battery(
        self,
        *,
        battery_id: str,
        client_id: str,
        name: Optional[str] = None,
        purpose: Optional[str] = None,
        generation_mode: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any] | None:
        return self._repo.update_battery(
            battery_id=battery_id,
            client_id=client_id,
            name=name,
            purpose=purpose,
            generation_mode=generation_mode,
            status=status,
        )

    def add_query(
        self,
        *,
        battery_id: str,
        query_text: str,
        query_type: Optional[str] = None,
        intent_archetype: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        weight: float = 1.0,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        return self._repo.add_query(
            battery_id=battery_id,
            query_text=query_text,
            query_type=query_type,
            intent_archetype=intent_archetype,
            constraints=constraints,
            weight=weight,
            enabled=enabled,
        )

    def list_queries(self, *, battery_id: str) -> list[Dict[str, Any]]:
        return self._repo.list_queries(battery_id=battery_id)

    def update_query(
        self,
        *,
        query_id: str,
        query_text: Optional[str] = None,
        query_type: Optional[str] = None,
        intent_archetype: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        weight: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> Dict[str, Any] | None:
        return self._repo.update_query(
            query_id=query_id,
            query_text=query_text,
            query_type=query_type,
            intent_archetype=intent_archetype,
            constraints=constraints,
            weight=weight,
            enabled=enabled,
        )


__all__ = ["QueryBatteryService"]
