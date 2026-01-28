from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from application.ports.deps import ClientsStore, PlatformProfilesStore


class AdminService:
    def __init__(
        self,
        *,
        clients_repo: ClientsStore,
        platform_profiles_repo: PlatformProfilesStore,
    ) -> None:
        self._clients = clients_repo
        self._platform_profiles = platform_profiles_repo

    def create_client(
        self, *, client_id: str, name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._clients.create_client(
            client_id=client_id, name=name, metadata=metadata or {}
        )

    def list_clients(self) -> list[Dict[str, Any]]:
        return self._clients.list_clients()

    def create_brand(
        self,
        *,
        brand_id: str,
        client_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._clients.create_brand(
            brand_id=brand_id, client_id=client_id, name=name, metadata=metadata or {}
        )

    def list_brands(self, *, client_id: str) -> list[Dict[str, Any]]:
        return self._clients.list_brands(client_id=client_id)

    def create_product(
        self,
        *,
        product_id: str,
        brand_id: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._clients.create_product(
            product_id=product_id,
            brand_id=brand_id,
            name=name,
            description=description,
            metadata=metadata or {},
        )

    def list_products(self, *, brand_id: str) -> list[Dict[str, Any]]:
        return self._clients.list_products(brand_id=brand_id)

    def add_client_user(
        self, *, client_id: str, member_user_id: str, role: Optional[str] = None
    ) -> Dict[str, Any]:
        return self._clients.add_client_user(
            client_id=client_id, user_id=member_user_id, role=role
        )

    def list_client_users(self, *, client_id: str) -> list[Dict[str, Any]]:
        return self._clients.list_client_users(client_id=client_id)

    def get_platform_profile(self) -> Dict[str, Any]:
        existing = self._platform_profiles.get_platform_profile()
        if existing:
            return existing
        fallback = _load_default_platform_profile()
        if not fallback:
            return {}
        return self._platform_profiles.ensure_platform_profile(
            name=fallback.get("name") or "UCP Platform Profile",
            version=fallback.get("version") or "2026-01-11",
            profile=fallback,
        )

    def ensure_platform_profile(
        self, *, name: str, version: str, profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._platform_profiles.ensure_platform_profile(
            name=name, version=version, profile=profile
        )

    def update_platform_profile(
        self, *, name: str, version: str, profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._platform_profiles.upsert_platform_profile(
            name=name, version=version, profile=profile
        )


def _load_default_platform_profile() -> Dict[str, Any] | None:
    path = Path("data/platform_profiles/ucp_platform_2026-01-11.json")
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
