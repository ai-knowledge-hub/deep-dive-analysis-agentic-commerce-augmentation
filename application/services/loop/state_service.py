from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import AppDeps


class StateService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def snapshot(
        self,
        *,
        client_id: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
        vertical: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        latest = self._deps.world_states.get_latest_world_state(
            client_id=client_id, brand_id=brand_id, product_id=product_id
        )
        next_version = int((latest or {}).get("version", 0)) + 1
        return self._deps.world_states.create_world_state_snapshot(
            client_id=client_id,
            brand_id=brand_id,
            product_id=product_id,
            vertical=vertical,
            state=state or {},
            version=next_version,
        )

    def latest(
        self,
        *,
        client_id: str,
        brand_id: Optional[str] = None,
        product_id: Optional[str] = None,
    ) -> Dict[str, Any] | None:
        return self._deps.world_states.get_latest_world_state(
            client_id=client_id, brand_id=brand_id, product_id=product_id
        )


__all__ = ["StateService"]
