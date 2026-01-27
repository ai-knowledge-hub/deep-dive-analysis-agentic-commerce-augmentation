from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.memory.repositories import clients as _repo


def create_client(
    *, client_id: str, name: str, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return _repo.create_client(client_id, name, metadata=metadata or {})


def list_clients() -> List[Dict[str, Any]]:
    return _repo.list_clients()


def create_brand(
    *, brand_id: str, client_id: str, name: str, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return _repo.create_brand(brand_id, client_id, name, metadata=metadata or {})


def list_brands(*, client_id: str) -> List[Dict[str, Any]]:
    return _repo.list_brands(client_id)


def create_product(
    *,
    product_id: str,
    brand_id: str,
    name: str,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _repo.create_product(
        product_id, brand_id, name, description=description, metadata=metadata or {}
    )


def list_products(*, brand_id: str) -> List[Dict[str, Any]]:
    return _repo.list_products(brand_id)


def get_product(*, product_id: str) -> Dict[str, Any] | None:
    return _repo.get_product(product_id)


def get_product_for_client(*, client_id: str, product_id: str) -> Dict[str, Any] | None:
    return _repo.get_product_for_client(client_id, product_id)


def search_products_for_client(
    *, client_id: str, query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    return _repo.search_products_for_client(client_id, query, limit=limit)


def add_client_user(
    *, client_id: str, user_id: str, role: Optional[str] = None
) -> Dict[str, Any]:
    return _repo.add_client_user(client_id, user_id, role)


def list_client_users(*, client_id: str) -> List[Dict[str, Any]]:
    return _repo.list_client_users(client_id)


__all__ = [
    "create_client",
    "list_clients",
    "create_brand",
    "list_brands",
    "create_product",
    "list_products",
    "get_product",
    "get_product_for_client",
    "search_products_for_client",
    "add_client_user",
    "list_client_users",
]
