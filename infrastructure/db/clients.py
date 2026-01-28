"""Client/brand/product repositories (tenancy-aware)."""

from __future__ import annotations

from typing import Any, Dict, List

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_client(
    *, client_id: str, name: str, metadata: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO clients (id, name, metadata_json)
        VALUES (?, ?, json(?))
        """,
        (client_id, name, to_json(metadata) or to_json({})),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _client_row(row)


def list_clients() -> List[Dict[str, Any]]:
    rows = get_connection().execute("SELECT * FROM clients ORDER BY name").fetchall()
    return [_client_row(row) for row in rows]


def create_brand(
    *, brand_id: str, client_id: str, name: str, metadata: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO brands (id, client_id, name, metadata_json)
        VALUES (?, ?, ?, json(?))
        """,
        (brand_id, client_id, name, to_json(metadata) or to_json({})),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    return _brand_row(row)


def list_brands(*, client_id: str) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute("SELECT * FROM brands WHERE client_id = ? ORDER BY name", (client_id,))
        .fetchall()
    )
    return [_brand_row(row) for row in rows]


def create_product(
    *,
    product_id: str,
    brand_id: str,
    name: str,
    description: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO products (id, brand_id, name, description, metadata_json)
        VALUES (?, ?, ?, ?, json(?))
        """,
        (product_id, brand_id, name, description, to_json(metadata) or to_json({})),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _product_row(row)


def list_products(*, brand_id: str) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute("SELECT * FROM products WHERE brand_id = ? ORDER BY name", (brand_id,))
        .fetchall()
    )
    return [_product_row(row) for row in rows]


def get_product(*, product_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM products WHERE id = ?", (product_id,))
        .fetchone()
    )
    return _product_row(row) if row else None


def get_brand(*, brand_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM brands WHERE id = ?", (brand_id,))
        .fetchone()
    )
    return _brand_row(row) if row else None


def get_product_for_client(*, client_id: str, product_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
            SELECT p.*
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            WHERE b.client_id = ? AND p.id = ?
            """,
            (client_id, product_id),
        )
        .fetchone()
    )
    return _product_row(row) if row else None


def search_products_for_client(
    *, client_id: str, query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    pattern = f"%{q}%"
    rows = (
        get_connection()
        .execute(
            """
            SELECT p.*
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            WHERE b.client_id = ?
              AND (
                lower(p.name) LIKE ?
                OR lower(coalesce(p.description, '')) LIKE ?
                OR lower(coalesce(p.metadata_json, '')) LIKE ?
              )
            ORDER BY p.created_at DESC
            LIMIT ?
            """,
            (client_id, pattern, pattern, pattern, limit),
        )
        .fetchall()
    )
    return [_product_row(row) for row in rows]


def add_client_user(
    *, client_id: str, user_id: str, role: str | None = None
) -> Dict[str, Any]:
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO client_users (client_id, user_id, role)
        VALUES (?, ?, ?)
        ON CONFLICT(client_id, user_id) DO UPDATE SET role = excluded.role
        """,
        (client_id, user_id, role or "analyst"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM client_users WHERE client_id = ? AND user_id = ?",
        (client_id, user_id),
    ).fetchone()
    return _client_user_row(row)


def list_client_users(*, client_id: str) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            "SELECT * FROM client_users WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
        )
        .fetchall()
    )
    return [_client_user_row(row) for row in rows]


def _client_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "metadata": from_json(row["metadata_json"], default={}),
        "created_at": row["created_at"],
    }


def _brand_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "name": row["name"],
        "metadata": from_json(row["metadata_json"], default={}),
        "created_at": row["created_at"],
    }


def _product_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "brand_id": row["brand_id"],
        "name": row["name"],
        "description": row["description"],
        "metadata": from_json(row["metadata_json"], default={}),
        "created_at": row["created_at"],
    }


def _client_user_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "user_id": row["user_id"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


__all__ = [
    "create_client",
    "list_clients",
    "create_brand",
    "list_brands",
    "create_product",
    "list_products",
    "get_brand",
    "get_product",
    "get_product_for_client",
    "search_products_for_client",
    "add_client_user",
    "list_client_users",
]
