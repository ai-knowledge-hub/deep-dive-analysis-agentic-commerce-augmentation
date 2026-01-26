from __future__ import annotations

from typing import Any, Dict, Optional

from infrastructure.db import clients as clients_repo


class AdminService:
    def create_client(
        self, *, client_id: str, name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return clients_repo.create_client(client_id=client_id, name=name, metadata=metadata or {})

    def list_clients(self) -> list[Dict[str, Any]]:
        return clients_repo.list_clients()

    def create_brand(
        self,
        *,
        brand_id: str,
        client_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return clients_repo.create_brand(
            brand_id=brand_id, client_id=client_id, name=name, metadata=metadata or {}
        )

    def list_brands(self, *, client_id: str) -> list[Dict[str, Any]]:
        return clients_repo.list_brands(client_id=client_id)

    def create_product(
        self,
        *,
        product_id: str,
        brand_id: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return clients_repo.create_product(
            product_id=product_id,
            brand_id=brand_id,
            name=name,
            description=description,
            metadata=metadata or {},
        )

    def list_products(self, *, brand_id: str) -> list[Dict[str, Any]]:
        return clients_repo.list_products(brand_id=brand_id)

    def add_client_user(
        self, *, client_id: str, member_user_id: str, role: Optional[str] = None
    ) -> Dict[str, Any]:
        return clients_repo.add_client_user(
            client_id=client_id, user_id=member_user_id, role=role
        )

    def list_client_users(self, *, client_id: str) -> list[Dict[str, Any]]:
        return clients_repo.list_client_users(client_id=client_id)
