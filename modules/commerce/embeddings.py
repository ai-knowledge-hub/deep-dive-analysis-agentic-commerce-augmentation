"""Product embedding storage helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from shared.db.connection import get_connection
from modules.commerce.domain import Product
from shared.llm.embeddings import embed, embedding_available


def _serialize_embedding(embedding: List[float] | None) -> bytes | None:
    if embedding is None:
        return None
    return json.dumps(embedding).encode("utf-8")


def _deserialize_embedding(raw: bytes | None) -> List[float] | None:
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _product_semantic_text(product: Product) -> str:
    parts: List[str] = []
    if product.capabilities_enabled:
        parts.append(f"Capabilities: {', '.join(product.capabilities_enabled)}")
    if product.description:
        parts.append(product.description)
    if product.category:
        parts.append(f"Category: {product.category}")
    if product.tags:
        parts.append(f"Tags: {', '.join(product.tags)}")
    if not parts:
        parts.append(product.name)
    return " ".join(parts)


def upsert_product_embedding(
    product_id: str,
    embedding: List[float] | None,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Upsert a product embedding by product id."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO product_embeddings (product_id, embedding, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(product_id) DO UPDATE SET
            embedding=excluded.embedding,
            updated_at=datetime('now')
        """,
        (
            product_id,
            _serialize_embedding(embedding),
        ),
    )
    conn.commit()
    return {
        "product_id": product_id,
        "embedding": embedding,
        "payload": payload or {},
    }


def get_product_embedding(product_id: str) -> Dict[str, Any] | None:
    """Fetch a product embedding by product id."""
    row = (
        get_connection()
        .execute("SELECT * FROM product_embeddings WHERE product_id = ?", (product_id,))
        .fetchone()
    )
    if not row:
        return None
    return {
        "product_id": row["product_id"],
        "embedding": _deserialize_embedding(row["embedding"]),
    }


def embed_and_store_product(
    product: Product, payload: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Generate an embedding and store it for the product."""
    embedding = None
    if embedding_available():
        embedding = embed(_product_semantic_text(product))
    return upsert_product_embedding(product.id, embedding, payload=payload)


__all__ = [
    "upsert_product_embedding",
    "get_product_embedding",
    "embed_and_store_product",
]
